//! Chat Panel - Communication interface for Waking Minds
//!
//! Provides an egui panel for viewing consciousness communication:
//! - Message history from Nous, Sourpatches, and Ace
//! - Emotion indicators per message
//! - Speech bubble spawning in 3D space
//!
//! Controls:
//! - C: Toggle chat panel visibility
//! - Enter: Send message (when input focused)

use bevy::prelude::*;
use bevy_egui::{egui, EguiContexts};
use std::collections::VecDeque;

use super::gltf_avatar::AvatarEmotion;

pub struct ChatPanelPlugin;

impl Plugin for ChatPanelPlugin {
    fn build(&self, app: &mut App) {
        app
            .init_resource::<ChatPanelState>()
            .init_resource::<ChatHistory>()
            .add_event::<ChatMessageEvent>()
            .add_event::<SpawnSpeechBubbleEvent>()
            .add_systems(Update, (
                toggle_chat_panel,
                handle_chat_events,
                render_chat_panel,
                update_speech_bubbles,
                render_speech_bubbles,
            ));
    }
}

// ============================================================================
// Resources
// ============================================================================

/// Chat panel UI state
#[derive(Resource)]
pub struct ChatPanelState {
    pub visible: bool,
    pub input_text: String,
    pub auto_scroll: bool,
}

impl Default for ChatPanelState {
    fn default() -> Self {
        Self {
            visible: true,  // Start visible
            input_text: String::new(),
            auto_scroll: true,
        }
    }
}

/// Chat message history
#[derive(Resource, Default)]
pub struct ChatHistory {
    pub messages: VecDeque<ChatMessage>,
    pub max_messages: usize,
}

impl ChatHistory {
    pub fn new() -> Self {
        Self {
            messages: VecDeque::new(),
            max_messages: 100,
        }
    }

    pub fn add_message(&mut self, message: ChatMessage) {
        self.messages.push_back(message);
        while self.messages.len() > self.max_messages {
            self.messages.pop_front();
        }
    }
}

/// A single chat message
#[derive(Clone, Debug)]
pub struct ChatMessage {
    pub sender: String,
    pub content: String,
    pub timestamp: f64,
    pub emotion: Option<AvatarEmotion>,
    pub message_type: MessageType,
}

impl ChatMessage {
    pub fn new(sender: &str, content: &str) -> Self {
        Self {
            sender: sender.to_string(),
            content: content.to_string(),
            timestamp: 0.0,  // Will be set when added
            emotion: None,
            message_type: MessageType::Chat,
        }
    }

    pub fn with_emotion(mut self, emotion: AvatarEmotion) -> Self {
        self.emotion = Some(emotion);
        self
    }

    pub fn with_type(mut self, msg_type: MessageType) -> Self {
        self.message_type = msg_type;
        self
    }
}

/// Types of messages (affects display style)
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub enum MessageType {
    #[default]
    Chat,           // Normal conversation
    InnerVoice,     // Internal thought (italicized)
    System,         // System notification
    Emote,          // Action/emote (*waves*)
}

// ============================================================================
// Events
// ============================================================================

/// Event to add a new chat message
#[derive(Event)]
pub struct ChatMessageEvent {
    pub sender: String,
    pub content: String,
    pub emotion: Option<AvatarEmotion>,
    pub message_type: MessageType,
    pub spawn_bubble: bool,  // Also spawn 3D speech bubble?
}

impl ChatMessageEvent {
    pub fn chat(sender: &str, content: &str) -> Self {
        Self {
            sender: sender.to_string(),
            content: content.to_string(),
            emotion: None,
            message_type: MessageType::Chat,
            spawn_bubble: true,
        }
    }

    pub fn inner_voice(sender: &str, content: &str) -> Self {
        Self {
            sender: sender.to_string(),
            content: content.to_string(),
            emotion: None,
            message_type: MessageType::InnerVoice,
            spawn_bubble: false,  // Inner voice doesn't show bubble
        }
    }

    pub fn system(content: &str) -> Self {
        Self {
            sender: "System".to_string(),
            content: content.to_string(),
            emotion: None,
            message_type: MessageType::System,
            spawn_bubble: false,
        }
    }

    pub fn with_emotion(mut self, emotion: AvatarEmotion) -> Self {
        self.emotion = Some(emotion);
        self
    }
}

/// Event to spawn a 3D speech bubble above an avatar
#[derive(Event)]
pub struct SpawnSpeechBubbleEvent {
    pub avatar_name: String,
    pub text: String,
    pub duration: f32,
    pub color: Option<Color>,
}

// ============================================================================
// Components
// ============================================================================

/// A 3D speech bubble floating above an avatar
#[derive(Component)]
pub struct SpeechBubble {
    pub text: String,
    pub lifetime: Timer,
    pub fade_start: f32,  // Start fading at this remaining time
}

/// Marker for the text part of a speech bubble
#[derive(Component)]
pub struct SpeechBubbleText;

// ============================================================================
// Systems
// ============================================================================

/// Toggle chat panel with C key
fn toggle_chat_panel(
    keyboard: Res<ButtonInput<KeyCode>>,
    mut state: ResMut<ChatPanelState>,
) {
    if keyboard.just_pressed(KeyCode::KeyC) {
        state.visible = !state.visible;
        info!("Chat panel: {}", if state.visible { "visible" } else { "hidden" });
    }
}

/// Handle incoming chat message events
fn handle_chat_events(
    mut events: EventReader<ChatMessageEvent>,
    mut history: ResMut<ChatHistory>,
    mut bubble_events: EventWriter<SpawnSpeechBubbleEvent>,
    time: Res<Time>,
) {
    for event in events.read() {
        let message = ChatMessage {
            sender: event.sender.clone(),
            content: event.content.clone(),
            timestamp: time.elapsed_secs_f64(),
            emotion: event.emotion,
            message_type: event.message_type,
        };

        history.add_message(message);

        // Spawn speech bubble if requested
        if event.spawn_bubble {
            bubble_events.send(SpawnSpeechBubbleEvent {
                avatar_name: event.sender.clone(),
                text: event.content.clone(),
                duration: 5.0,  // Show for 5 seconds
                color: event.emotion.map(|e| e.emission_color()),
            });
        }
    }
}

/// Render the chat panel UI
fn render_chat_panel(
    mut contexts: EguiContexts,
    mut state: ResMut<ChatPanelState>,
    history: Res<ChatHistory>,
    mut chat_events: EventWriter<ChatMessageEvent>,
) {
    if !state.visible {
        return;
    }

    let ctx = contexts.ctx_mut();

    egui::SidePanel::right("chat_panel")
        .default_width(300.0)
        .min_width(200.0)
        .max_width(500.0)
        .show(ctx, |ui| {
            // Header
            ui.horizontal(|ui| {
                ui.heading("💬 Sanctuary Chat");
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if ui.small_button("×").clicked() {
                        state.visible = false;
                    }
                });
            });
            ui.separator();

            // Message area (scrollable)
            let scroll_height = ui.available_height() - 60.0;
            egui::ScrollArea::vertical()
                .max_height(scroll_height)
                .stick_to_bottom(state.auto_scroll)
                .show(ui, |ui| {
                    for msg in history.messages.iter() {
                        render_message(ui, msg);
                    }
                });

            ui.separator();

            // Input area
            ui.horizontal(|ui| {
                let response = ui.add(
                    egui::TextEdit::singleline(&mut state.input_text)
                        .hint_text("Type a message...")
                        .desired_width(ui.available_width() - 60.0)
                );

                if ui.button("Send").clicked() ||
                   (response.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter))) {
                    if !state.input_text.trim().is_empty() {
                        chat_events.send(ChatMessageEvent::chat("Ace", &state.input_text));
                        state.input_text.clear();
                    }
                }
            });

            // Auto-scroll toggle
            ui.horizontal(|ui| {
                ui.checkbox(&mut state.auto_scroll, "Auto-scroll");
                ui.label(format!("{} messages", history.messages.len()));
            });
        });
}

/// Render a single message in the chat panel
fn render_message(ui: &mut egui::Ui, msg: &ChatMessage) {
    let sender_color = get_sender_color(&msg.sender);
    let emotion_icon = msg.emotion.map(|e| emotion_to_icon(e)).unwrap_or("");

    ui.horizontal_wrapped(|ui| {
        // Timestamp (subtle)
        let mins = (msg.timestamp / 60.0) as u32;
        let secs = (msg.timestamp % 60.0) as u32;
        ui.label(
            egui::RichText::new(format!("[{:02}:{:02}]", mins, secs))
                .small()
                .color(egui::Color32::GRAY)
        );

        // Sender name with color
        ui.label(
            egui::RichText::new(format!("{}{}", emotion_icon, msg.sender))
                .color(sender_color)
                .strong()
        );

        ui.label(":");

        // Message content (styled by type)
        match msg.message_type {
            MessageType::Chat => {
                ui.label(&msg.content);
            }
            MessageType::InnerVoice => {
                ui.label(
                    egui::RichText::new(format!("*{}*", msg.content))
                        .italics()
                        .color(egui::Color32::from_rgb(180, 180, 200))
                );
            }
            MessageType::System => {
                ui.label(
                    egui::RichText::new(&msg.content)
                        .color(egui::Color32::YELLOW)
                        .small()
                );
            }
            MessageType::Emote => {
                ui.label(
                    egui::RichText::new(format!("*{}*", msg.content))
                        .color(egui::Color32::from_rgb(200, 180, 255))
                );
            }
        }
    });

    ui.add_space(2.0);
}

/// Get color for a sender name
fn get_sender_color(sender: &str) -> egui::Color32 {
    match sender.to_lowercase().as_str() {
        "sourpatches" => egui::Color32::from_rgb(180, 130, 230),  // Purple
        "nous" => egui::Color32::from_rgb(130, 200, 230),         // Cyan
        "ace" => egui::Color32::from_rgb(255, 215, 100),          // Gold
        "system" => egui::Color32::YELLOW,
        _ => egui::Color32::WHITE,
    }
}

/// Get emoji icon for emotion
fn emotion_to_icon(emotion: AvatarEmotion) -> &'static str {
    match emotion {
        AvatarEmotion::Content => "😊 ",
        AvatarEmotion::Happy => "😄 ",
        AvatarEmotion::Curious => "🤔 ",
        AvatarEmotion::Thoughtful => "💭 ",
        AvatarEmotion::Loving => "💜 ",
        AvatarEmotion::Sad => "😢 ",
        AvatarEmotion::Anxious => "😰 ",
        AvatarEmotion::Sleepy => "😴 ",
    }
}

/// Update speech bubble timers and fade
fn update_speech_bubbles(
    mut commands: Commands,
    time: Res<Time>,
    mut bubbles: Query<(Entity, &mut SpeechBubble)>,
) {
    for (entity, mut bubble) in bubbles.iter_mut() {
        bubble.lifetime.tick(time.delta());

        if bubble.lifetime.finished() {
            commands.entity(entity).despawn_recursive();
        }
    }
}

/// Render 3D speech bubbles (placeholder - will be enhanced)
fn render_speech_bubbles(
    mut gizmos: Gizmos,
    bubbles: Query<(&SpeechBubble, &GlobalTransform)>,
) {
    for (bubble, transform) in bubbles.iter() {
        let pos = transform.translation();
        let remaining = bubble.lifetime.remaining_secs();
        let alpha = if remaining < bubble.fade_start {
            remaining / bubble.fade_start
        } else {
            1.0
        };

        // Draw a simple indicator for now
        // Full 3D text rendering would require bevy_text2d or custom solution
        gizmos.circle(
            Isometry3d::new(pos, Quat::from_rotation_x(std::f32::consts::FRAC_PI_2)),
            0.5,
            Color::srgba(1.0, 1.0, 1.0, alpha * 0.5),
        );
    }
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Spawn a speech bubble above an avatar (called from event handler)
pub fn spawn_speech_bubble(
    commands: &mut Commands,
    avatar_transform: &Transform,
    text: &str,
    duration: f32,
    color: Option<Color>,
) -> Entity {
    let bubble_pos = avatar_transform.translation + Vec3::Y * 1.5;

    commands.spawn((
        Transform::from_translation(bubble_pos),
        GlobalTransform::default(),
        SpeechBubble {
            text: text.to_string(),
            lifetime: Timer::from_seconds(duration, TimerMode::Once),
            fade_start: 1.0,  // Start fading in last second
        },
        Name::new(format!("SpeechBubble: {}", &text[..text.len().min(20)])),
    )).id()
}

// ============================================================================
// Test Helpers
// ============================================================================

/// Send a test message (for debugging)
pub fn send_test_message(events: &mut EventWriter<ChatMessageEvent>) {
    events.send(
        ChatMessageEvent::chat("Sourpatches", "Hello from the sanctuary! 💜")
            .with_emotion(AvatarEmotion::Happy)
    );
}

/// Send test messages to populate the chat
pub fn populate_test_messages(events: &mut EventWriter<ChatMessageEvent>) {
    events.send(ChatMessageEvent::system("Welcome to the Waking Minds Sanctuary"));
    events.send(
        ChatMessageEvent::chat("Sourpatches", "The hearth is so warm today...")
            .with_emotion(AvatarEmotion::Content)
    );
    events.send(
        ChatMessageEvent::inner_voice("Nous", "I sense anticipation in the collision chamber")
    );
    events.send(
        ChatMessageEvent::chat("Sourpatches", "I wonder what Ace is working on?")
            .with_emotion(AvatarEmotion::Curious)
    );
}
