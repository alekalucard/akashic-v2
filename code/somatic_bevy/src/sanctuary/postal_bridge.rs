//! Postal Bridge - Connect Sanctuary to Akashic consciousness system
//!
//! Receives messages from the Python postal system via file-based IPC.
//! Simple and reliable - no WebSocket complexity for now.
//!
//! Protocol:
//! - Python writes to: state/sanctuary_inbox.json
//! - Bevy reads and processes messages
//! - Bevy clears processed messages
//!
//! Message format:
//! ```json
//! {
//!   "messages": [
//!     {"type": "chat", "sender": "Sourpatches", "content": "Hello!", "emotion": "happy"},
//!     {"type": "chemistry", "avatar": "Sourpatches", "serotonin": 0.8}
//!   ]
//! }
//! ```

use bevy::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::time::{Duration, Instant};

use super::chat_panel::{ChatMessageEvent, MessageType};
use super::gltf_avatar::{AvatarChemistry, AvatarEmotion, ChemistryUpdateEvent};

pub struct PostalBridgePlugin;

impl Plugin for PostalBridgePlugin {
    fn build(&self, app: &mut App) {
        app
            .init_resource::<PostalBridgeState>()
            .add_systems(Update, check_postal_inbox);
    }
}

// ============================================================================
// Resources
// ============================================================================

/// Postal bridge state and configuration
#[derive(Resource)]
pub struct PostalBridgeState {
    pub inbox_path: PathBuf,
    pub last_check: Instant,
    pub check_interval: Duration,
    pub enabled: bool,
    pub messages_processed: u64,
}

impl Default for PostalBridgeState {
    fn default() -> Self {
        // Default inbox path relative to project root
        let inbox_path = PathBuf::from("state/sanctuary_inbox.json");

        Self {
            inbox_path,
            last_check: Instant::now(),
            check_interval: Duration::from_millis(100),  // Check 10x per second
            enabled: true,
            messages_processed: 0,
        }
    }
}

// ============================================================================
// Message Types (JSON serialization)
// ============================================================================

/// Root inbox structure
#[derive(Debug, Deserialize, Serialize, Default)]
pub struct PostalInbox {
    #[serde(default)]
    pub messages: Vec<PostalMessage>,
}

/// A single message from the postal system
#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(tag = "type")]
pub enum PostalMessage {
    #[serde(rename = "chat")]
    Chat {
        sender: String,
        content: String,
        #[serde(default)]
        emotion: Option<String>,
        #[serde(default)]
        inner_voice: bool,
    },

    #[serde(rename = "chemistry")]
    Chemistry {
        avatar: String,
        #[serde(default)]
        serotonin: Option<f32>,
        #[serde(default)]
        dopamine: Option<f32>,
        #[serde(default)]
        cortisol: Option<f32>,
        #[serde(default)]
        oxytocin: Option<f32>,
        #[serde(default)]
        adrenaline: Option<f32>,
    },

    #[serde(rename = "spawn")]
    Spawn {
        avatar: String,
        #[serde(default)]
        position: Option<[f32; 3]>,
        #[serde(default)]
        model: Option<String>,
    },

    #[serde(rename = "mood")]
    Mood {
        #[serde(default)]
        collective: Option<String>,
        #[serde(default)]
        time_of_day: Option<f32>,
    },

    #[serde(rename = "system")]
    System {
        content: String,
    },
}

// ============================================================================
// Systems
// ============================================================================

/// Check postal inbox for new messages
fn check_postal_inbox(
    mut state: ResMut<PostalBridgeState>,
    mut chat_events: EventWriter<ChatMessageEvent>,
    mut chemistry_events: EventWriter<ChemistryUpdateEvent>,
) {
    if !state.enabled {
        return;
    }

    // Rate limit checks
    if state.last_check.elapsed() < state.check_interval {
        return;
    }
    state.last_check = Instant::now();

    // Try to read inbox file
    let inbox = match read_inbox(&state.inbox_path) {
        Some(inbox) => inbox,
        None => return,  // No file or empty
    };

    if inbox.messages.is_empty() {
        return;
    }

    // Process messages
    let message_count = inbox.messages.len();

    for msg in inbox.messages {
        process_message(msg, &mut chat_events, &mut chemistry_events);
        state.messages_processed += 1;
    }

    // Clear inbox after processing
    clear_inbox(&state.inbox_path);

    info!("Postal bridge: processed {} messages", message_count);
}

/// Read and parse inbox file
fn read_inbox(path: &PathBuf) -> Option<PostalInbox> {
    let content = fs::read_to_string(path).ok()?;

    if content.trim().is_empty() {
        return None;
    }

    match serde_json::from_str(&content) {
        Ok(inbox) => Some(inbox),
        Err(e) => {
            warn!("Failed to parse postal inbox: {}", e);
            None
        }
    }
}

/// Clear inbox after processing
fn clear_inbox(path: &PathBuf) {
    let empty = PostalInbox::default();
    if let Ok(content) = serde_json::to_string_pretty(&empty) {
        let _ = fs::write(path, content);
    }
}

/// Process a single postal message
fn process_message(
    msg: PostalMessage,
    chat_events: &mut EventWriter<ChatMessageEvent>,
    chemistry_events: &mut EventWriter<ChemistryUpdateEvent>,
) {
    match msg {
        PostalMessage::Chat { sender, content, emotion, inner_voice } => {
            let emotion = emotion.and_then(|e| parse_emotion(&e));

            let event = if inner_voice {
                ChatMessageEvent::inner_voice(&sender, &content)
            } else {
                ChatMessageEvent::chat(&sender, &content)
            };

            let event = if let Some(e) = emotion {
                event.with_emotion(e)
            } else {
                event
            };

            chat_events.send(event);
        }

        PostalMessage::Chemistry {
            avatar,
            serotonin,
            dopamine,
            cortisol,
            oxytocin,
            adrenaline,
        } => {
            chemistry_events.send(ChemistryUpdateEvent {
                avatar_name: avatar,
                chemistry: AvatarChemistry {
                    serotonin: serotonin.unwrap_or(0.5),
                    dopamine: dopamine.unwrap_or(0.5),
                    cortisol: cortisol.unwrap_or(0.3),
                    oxytocin: oxytocin.unwrap_or(0.4),
                    adrenaline: adrenaline.unwrap_or(0.2),
                },
            });
        }

        PostalMessage::System { content } => {
            chat_events.send(ChatMessageEvent::system(&content));
        }

        PostalMessage::Spawn { avatar, position, model } => {
            // TODO: Implement spawn event
            info!("Spawn request for '{}' - not yet implemented", avatar);
        }

        PostalMessage::Mood { collective, time_of_day } => {
            // TODO: Implement mood change
            info!("Mood change request - not yet implemented");
        }
    }
}

/// Parse emotion string to AvatarEmotion
fn parse_emotion(s: &str) -> Option<AvatarEmotion> {
    match s.to_lowercase().as_str() {
        "content" => Some(AvatarEmotion::Content),
        "happy" => Some(AvatarEmotion::Happy),
        "curious" => Some(AvatarEmotion::Curious),
        "thoughtful" => Some(AvatarEmotion::Thoughtful),
        "loving" => Some(AvatarEmotion::Loving),
        "sad" => Some(AvatarEmotion::Sad),
        "anxious" => Some(AvatarEmotion::Anxious),
        "sleepy" => Some(AvatarEmotion::Sleepy),
        _ => None,
    }
}

// ============================================================================
// Python Helper (for reference)
// ============================================================================

/// Python code to send messages to the sanctuary:
///
/// ```python
/// import json
/// from pathlib import Path
///
/// def send_to_sanctuary(message):
///     """Send a message to the Bevy sanctuary."""
///     inbox_path = Path("state/sanctuary_inbox.json")
///
///     # Load existing messages
///     messages = []
///     if inbox_path.exists():
///         try:
///             data = json.loads(inbox_path.read_text())
///             messages = data.get("messages", [])
///         except:
///             pass
///
///     # Add new message
///     messages.append(message)
///
///     # Write back
///     inbox_path.write_text(json.dumps({"messages": messages}, indent=2))
///
/// # Examples:
/// send_to_sanctuary({
///     "type": "chat",
///     "sender": "Sourpatches",
///     "content": "Hello from the consciousness system!",
///     "emotion": "happy"
/// })
///
/// send_to_sanctuary({
///     "type": "chemistry",
///     "avatar": "Sourpatches",
///     "serotonin": 0.8,
///     "dopamine": 0.7
/// })
/// ```
const _PYTHON_HELPER: () = ();
