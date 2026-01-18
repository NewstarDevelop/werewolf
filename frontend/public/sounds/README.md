# Sound Assets

This directory contains audio files used in the application.

## Required Files

The following audio files are needed:

### UI Interaction
- `ui_click.mp3` - Button click sound
- `ui_hover.mp3` - Hover effect sound
- `notification.mp3` - Notification alert sound

### Game Phases
- `day_start.mp3` - Day phase background music (loop)
- `night_start.mp3` - Night phase background music (loop)

### Game Events
- `vote_cast.mp3` - Voting action sound
- `player_death.mp3` - Player elimination sound
- `victory.mp3` - Victory celebration music
- `defeat.mp3` - Defeat music

## File Format

- Primary format: MP3 (best browser compatibility)
- Alternative: WAV (for higher quality)
- Fallback support configured in `src/config/soundConfig.ts`

## Adding New Sounds

1. Place audio files in this directory (`frontend/public/sounds/`)
2. Update `src/config/soundConfig.ts` to register the new sound
3. File paths should be relative to `/public/` (e.g., `/sounds/filename.mp3`)

## Placeholder Files

For development, you can use silence or royalty-free sound effects from:
- https://freesound.org/
- https://pixabay.com/music/
- https://mixkit.co/free-sound-effects/

## License

Ensure all audio files have appropriate licensing for your use case.
