use crate::error::{DaemonError, Result};
use crate::events::ActivityEvent;
use rusqlite::{params, Connection};
use std::path::Path;

pub struct EventBuffer {
    conn: Connection,
}

impl EventBuffer {
    pub fn open(path: &Path) -> Result<Self> {
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;",
        )?;
        conn.execute(
            "CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )",
            [],
        )?;
        Ok(Self { conn })
    }

    pub fn insert(&self, event: &ActivityEvent) -> Result<()> {
        let payload = serde_json::to_string(event)?;
        self.conn.execute(
            "INSERT OR IGNORE INTO events (id, payload) VALUES (?1, ?2)",
            params![event.id.to_string(), payload],
        )?;
        Ok(())
    }

    pub fn read_batch(&self, limit: usize) -> Result<Vec<(String, ActivityEvent)>> {
        let mut stmt = self
            .conn
            .prepare("SELECT id, payload FROM events ORDER BY created_at ASC LIMIT ?1")?;
        let rows = stmt.query_map(params![limit as i64], |row| {
            let id: String = row.get(0)?;
            let payload: String = row.get(1)?;
            Ok((id, payload))
        })?;

        let mut results = Vec::new();
        for row in rows {
            let (id, payload) = row?;
            let event: ActivityEvent = serde_json::from_str(&payload)
                .map_err(|e| DaemonError::Buffer(format!("Failed to deserialize event: {e}")))?;
            results.push((id, event));
        }
        Ok(results)
    }

    pub fn delete_batch(&self, ids: &[String]) -> Result<()> {
        if ids.is_empty() {
            return Ok(());
        }
        let placeholders: Vec<String> = ids.iter().enumerate().map(|(i, _)| format!("?{}", i + 1)).collect();
        let sql = format!("DELETE FROM events WHERE id IN ({})", placeholders.join(","));
        let params: Vec<&dyn rusqlite::types::ToSql> =
            ids.iter().map(|id| id as &dyn rusqlite::types::ToSql).collect();
        self.conn.execute(&sql, params.as_slice())?;
        Ok(())
    }

    pub fn count(&self) -> Result<usize> {
        let count: i64 = self
            .conn
            .query_row("SELECT COUNT(*) FROM events", [], |row| row.get(0))?;
        Ok(count as usize)
    }

    pub fn cleanup_old(&self, max_age_days: u32) -> Result<usize> {
        let deleted = self.conn.execute(
            "DELETE FROM events WHERE created_at < datetime('now', ?1)",
            params![format!("-{max_age_days} days")],
        )?;
        Ok(deleted)
    }

    pub fn cleanup_excess(&self, max_count: usize) -> Result<usize> {
        let count = self.count()?;
        if count <= max_count {
            return Ok(0);
        }
        let excess = count - max_count;
        let deleted = self.conn.execute(
            "DELETE FROM events WHERE id IN (
                SELECT id FROM events ORDER BY created_at ASC LIMIT ?1
            )",
            params![excess as i64],
        )?;
        Ok(deleted)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::events::{EventType, WindowInfo};
    use tempfile::TempDir;

    fn make_buffer() -> (TempDir, EventBuffer) {
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("test_buffer.db");
        let buffer = EventBuffer::open(&path).unwrap();
        (dir, buffer)
    }

    fn make_event() -> ActivityEvent {
        ActivityEvent::window_change(WindowInfo {
            app_name: "Firefox".into(),
            window_title: "Test".into(),
            url: None,
        })
    }

    #[test]
    fn test_insert_and_count() {
        let (_dir, buffer) = make_buffer();
        assert_eq!(buffer.count().unwrap(), 0);
        buffer.insert(&make_event()).unwrap();
        assert_eq!(buffer.count().unwrap(), 1);
        buffer.insert(&make_event()).unwrap();
        assert_eq!(buffer.count().unwrap(), 2);
    }

    #[test]
    fn test_insert_duplicate_ignored() {
        let (_dir, buffer) = make_buffer();
        let event = make_event();
        buffer.insert(&event).unwrap();
        buffer.insert(&event).unwrap(); // same ID
        assert_eq!(buffer.count().unwrap(), 1);
    }

    #[test]
    fn test_read_batch() {
        let (_dir, buffer) = make_buffer();
        for _ in 0..5 {
            buffer.insert(&make_event()).unwrap();
        }
        let batch = buffer.read_batch(3).unwrap();
        assert_eq!(batch.len(), 3);
        assert_eq!(batch[0].1.event_type, EventType::WindowChange);
    }

    #[test]
    fn test_read_batch_empty() {
        let (_dir, buffer) = make_buffer();
        let batch = buffer.read_batch(10).unwrap();
        assert!(batch.is_empty());
    }

    #[test]
    fn test_delete_batch() {
        let (_dir, buffer) = make_buffer();
        for _ in 0..3 {
            buffer.insert(&make_event()).unwrap();
        }
        let batch = buffer.read_batch(2).unwrap();
        let ids: Vec<String> = batch.into_iter().map(|(id, _)| id).collect();
        buffer.delete_batch(&ids).unwrap();
        assert_eq!(buffer.count().unwrap(), 1);
    }

    #[test]
    fn test_delete_empty_batch() {
        let (_dir, buffer) = make_buffer();
        buffer.delete_batch(&[]).unwrap(); // should not error
    }

    #[test]
    fn test_cleanup_excess() {
        let (_dir, buffer) = make_buffer();
        for _ in 0..10 {
            buffer.insert(&make_event()).unwrap();
        }
        let removed = buffer.cleanup_excess(5).unwrap();
        assert_eq!(removed, 5);
        assert_eq!(buffer.count().unwrap(), 5);
    }

    #[test]
    fn test_cleanup_excess_no_op() {
        let (_dir, buffer) = make_buffer();
        for _ in 0..3 {
            buffer.insert(&make_event()).unwrap();
        }
        let removed = buffer.cleanup_excess(10).unwrap();
        assert_eq!(removed, 0);
        assert_eq!(buffer.count().unwrap(), 3);
    }

    #[test]
    fn test_serde_roundtrip_through_buffer() {
        let (_dir, buffer) = make_buffer();
        let event = ActivityEvent::idle_end(42);
        buffer.insert(&event).unwrap();
        let batch = buffer.read_batch(1).unwrap();
        assert_eq!(batch[0].1.id, event.id);
        assert_eq!(batch[0].1.event_type, EventType::IdleEnd);
        assert_eq!(batch[0].1.idle_duration_secs, Some(42));
    }
}
