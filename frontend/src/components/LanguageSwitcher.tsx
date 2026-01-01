import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Languages } from 'lucide-react';

export const LanguageSwitcher = () => {
  const { i18n, t } = useTranslation('common');

  const toggleLanguage = () => {
    const newLang = i18n.language === 'zh' ? 'en' : 'zh';
    i18n.changeLanguage(newLang);
  };

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleLanguage}
      className="gap-2"
      title={t('language.switch_hint')}
    >
      <Languages className="w-4 h-4" />
      {i18n.language === 'zh' ? 'English' : '中文'}
    </Button>
  );
};
