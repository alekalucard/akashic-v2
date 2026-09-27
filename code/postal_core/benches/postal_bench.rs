//! Benchmarks for postal_core
//!
//! Run with: cargo bench

use criterion::{black_box, criterion_group, criterion_main, Criterion, Throughput};
use postal_core::{Envelope, TopicBus, Priority};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

fn bench_envelope_creation(c: &mut Criterion) {
    c.bench_function("envelope_create", |b| {
        b.iter(|| {
            Envelope::new(
                black_box("test.action"),
                black_box(serde_json::json!({"key": "value"})),
            )
        })
    });
}

fn bench_publish_throughput(c: &mut Criterion) {
    let mut group = c.benchmark_group("publish_throughput");
    group.throughput(Throughput::Elements(1));

    let bus = TopicBus::new();
    let counter = Arc::new(AtomicUsize::new(0));
    let counter_clone = Arc::clone(&counter);

    bus.subscribe(
        "bench",
        move |_| {
            counter_clone.fetch_add(1, Ordering::Relaxed);
        },
        "bench-handler",
        0,
        1,
    );

    group.bench_function("single_publish", |b| {
        b.iter(|| {
            let env = Envelope::new("bench.action", serde_json::json!({}));
            bus.publish(env);
        })
    });

    group.finish();
}

fn bench_priority_ordering(c: &mut Criterion) {
    let bus = TopicBus::new();
    let received = Arc::new(std::sync::Mutex::new(Vec::new()));
    let received_clone = Arc::clone(&received);

    bus.subscribe(
        "priority",
        move |env| {
            received_clone.lock().unwrap().push(env.priority);
        },
        "priority-handler",
        0,
        1,
    );

    c.bench_function("mixed_priority_publish", |b| {
        b.iter(|| {
            // Publish in reverse priority order
            for p in [Priority::Low, Priority::Normal, Priority::High] {
                let env = Envelope::new("priority.test", serde_json::json!({}))
                    .with_priority(p);
                bus.publish(env);
            }
        })
    });
}

criterion_group!(
    benches,
    bench_envelope_creation,
    bench_publish_throughput,
    bench_priority_ordering,
);
criterion_main!(benches);
