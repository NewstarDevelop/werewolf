/**
 * SoundSettings Component
 * Settings panel for audio preferences
 */
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Volume2, VolumeX, Play } from 'lucide-react';
import { useSound } from '@/contexts/SoundContext';
import { useTranslation } from 'react-i18next';

export function SoundSettings() {
  const { t } = useTranslation('common');
  const {
    masterVolume,
    isMuted,
    isEnabled,
    setMasterVolume,
    setIsMuted,
    setIsEnabled,
    play,
  } = useSound();

  const handleVolumeChange = (values: number[]) => {
    setMasterVolume(values[0] / 100);
  };

  const handleTestSound = () => {
    play('CLICK');
  };

  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-accent-foreground">
          {isMuted ? (
            <VolumeX className="h-5 w-5" aria-hidden="true" />
          ) : (
            <Volume2 className="h-5 w-5" aria-hidden="true" />
          )}
          {t('settings.sound', 'Sound')}
        </CardTitle>
        <CardDescription>
          {t('settings.sound_desc', 'Configure audio preferences.')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Master Switch */}
        <div className="flex items-center justify-between rounded-lg border border-border p-4">
          <div className="space-y-1">
            <p className="text-sm font-medium">
              {t('settings.sound_effects', 'Sound Effects')}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('settings.sound_effects_desc', 'Game sound effects and notifications')}
            </p>
          </div>
          <Switch
            checked={isEnabled}
            onCheckedChange={setIsEnabled}
            aria-label={t('settings.sound_effects', 'Sound Effects')}
          />
        </div>

        {/* Volume Control */}
        <div className="space-y-4 opacity-100 transition-opacity" style={{ opacity: isEnabled ? 1 : 0.5 }}>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="volume-slider">
                {t('settings.volume', 'Volume')}
              </Label>
              <span className="text-sm text-muted-foreground">
                {Math.round(masterVolume * 100)}%
              </span>
            </div>
            <Slider
              id="volume-slider"
              value={[masterVolume * 100]}
              onValueChange={handleVolumeChange}
              max={100}
              step={1}
              disabled={!isEnabled}
              className="w-full"
              aria-label={t('settings.volume', 'Volume')}
            />
          </div>

          {/* Mute Toggle */}
          <div className="flex items-center justify-between rounded-lg border border-border p-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">
                {t('settings.mute', 'Mute')}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('settings.mute_desc', 'Mute all sounds')}
              </p>
            </div>
            <Switch
              checked={isMuted}
              onCheckedChange={setIsMuted}
              disabled={!isEnabled}
              aria-label={t('settings.mute', 'Mute')}
            />
          </div>

          {/* Test Sound Button */}
          <div className="pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTestSound}
              disabled={!isEnabled || isMuted}
              className="w-full"
            >
              <Play className="h-4 w-4 mr-2" />
              {t('settings.test_sound', 'Test Sound')}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
