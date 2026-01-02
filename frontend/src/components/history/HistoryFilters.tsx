import { useTranslation } from 'react-i18next';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';

interface HistoryFiltersProps {
  selectedWinner: string | undefined;
  onWinnerChange: (winner: string | undefined) => void;
}

export function HistoryFilters({ selectedWinner, onWinnerChange }: HistoryFiltersProps) {
  const { t } = useTranslation('common');

  const handleValueChange = (value: string) => {
    if (value === 'all') {
      onWinnerChange(undefined);
    } else {
      onWinnerChange(value);
    }
  };

  const currentValue = selectedWinner || 'all';

  return (
    <div className="bg-card/30 border border-border rounded-lg p-4 backdrop-blur-sm">
      <h3 className="text-sm font-semibold mb-3">{t('history.filter_by_winner')}</h3>
      <RadioGroup value={currentValue} onValueChange={handleValueChange}>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="all" id="filter-all" />
          <Label htmlFor="filter-all" className="cursor-pointer">
            {t('history.winner_all')}
          </Label>
        </div>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="werewolf" id="filter-werewolf" />
          <Label htmlFor="filter-werewolf" className="cursor-pointer">
            {t('history.winner_werewolf')}
          </Label>
        </div>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="villager" id="filter-villager" />
          <Label htmlFor="filter-villager" className="cursor-pointer">
            {t('history.winner_villager')}
          </Label>
        </div>
      </RadioGroup>
    </div>
  );
}
