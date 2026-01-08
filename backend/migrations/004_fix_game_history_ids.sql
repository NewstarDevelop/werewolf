-- Fix game history ID mismatch and clean invalid records
-- Migration for fixing game_sessions and game_participants data
-- Database: SQLite

-- Problem 1: game_sessions.id was using random UUID[:8] instead of room_id
-- This caused game_participants to reference non-existent game sessions

-- Step 1: Identify affected sessions (8-character IDs)
-- These need to be fixed to match their room_id
UPDATE game_sessions SET id = room_id WHERE length(id) = 8 AND id != room_id;

-- Step 2: Delete orphaned participant records
-- Participants whose game_id doesn't match any session
DELETE FROM game_participants
WHERE game_id NOT IN (SELECT id FROM game_sessions);

-- Step 3: Remove duplicate game_sessions
-- Keep only the one with correct id=room_id
DELETE FROM game_sessions
WHERE id IN (
    SELECT id FROM (
        SELECT id, room_id, ROW_NUMBER() OVER (PARTITION BY room_id ORDER BY created_at DESC) as rn
        FROM game_sessions
        WHERE room_id IS NOT NULL
    ) WHERE rn > 1
);

-- Step 4: Vacuum to rebuild database and reclaim space
VACUUM;

-- Verification queries
-- Check that all game_sessions have id=room_id (except deleted rooms)
SELECT COUNT(*) as mismatched_count
FROM game_sessions
WHERE id != room_id AND room_id IS NOT NULL;
-- Expected: 0

-- Check for orphaned participants
SELECT COUNT(*) as orphaned_count
FROM game_participants
WHERE game_id NOT IN (SELECT id FROM game_sessions);
-- Expected: 0

-- Display summary
SELECT
    (SELECT COUNT(*) FROM game_sessions) as total_sessions,
    (SELECT COUNT(*) FROM game_participants) as total_participants,
    (SELECT COUNT(DISTINCT user_id) FROM game_participants WHERE user_id IS NOT NULL) as unique_players;
