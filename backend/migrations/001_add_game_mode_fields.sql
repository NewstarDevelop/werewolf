-- Phase 8: Add game_mode and wolf_king_variant fields to rooms table
-- Migration for 12-player Werewolf support
-- Database: SQLite

-- Add game_mode column (default: classic_9 for backward compatibility)
ALTER TABLE rooms ADD COLUMN game_mode VARCHAR(20) DEFAULT 'classic_9' NOT NULL;

-- Add wolf_king_variant column (nullable, only used for 12-player mode)
ALTER TABLE rooms ADD COLUMN wolf_king_variant VARCHAR(20);

-- Update existing rooms to have explicit game_mode based on max_players
-- Existing rooms with max_players = 9 are classic_9 mode
UPDATE rooms SET game_mode = 'classic_9' WHERE max_players = 9;

-- Existing rooms with max_players = 12 (if any) default to wolf_king variant
-- Note: There should be no existing 12-player rooms before this migration
UPDATE rooms SET game_mode = 'classic_12', wolf_king_variant = 'wolf_king' WHERE max_players = 12;

-- Verify migration
-- Expected: All rooms have non-null game_mode
-- Expected: 12-player rooms have non-null wolf_king_variant
SELECT id, name, max_players, game_mode, wolf_king_variant FROM rooms;
