import { Moon, Sun, Palette, Monitor } from "lucide-react"
import { useTheme } from "next-themes"
import { useTranslation } from "react-i18next"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function ThemeSwitcher() {
  const { setTheme, theme } = useTheme()
  const { t } = useTranslation("common")

  const getThemeIcon = (value: string | undefined) => {
    switch (value) {
      case "light":
        return <Sun className="h-4 w-4" aria-hidden="true" />
      case "dark":
        return <Moon className="h-4 w-4" aria-hidden="true" />
      case "gray":
        return <Palette className="h-4 w-4" aria-hidden="true" />
      default:
        return <Monitor className="h-4 w-4" aria-hidden="true" />
    }
  }

  return (
    <Select value={theme} onValueChange={setTheme}>
      <SelectTrigger className="w-[140px]">
        <div className="flex items-center gap-2">
          {getThemeIcon(theme)}
          <SelectValue placeholder={t("settings.select_theme", "Select theme")} />
        </div>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="light">
          <div className="flex items-center gap-2">
            <Sun className="h-4 w-4" aria-hidden="true" />
            <span>{t("settings.theme_light", "Light")}</span>
          </div>
        </SelectItem>
        <SelectItem value="dark">
          <div className="flex items-center gap-2">
            <Moon className="h-4 w-4" aria-hidden="true" />
            <span>{t("settings.theme_dark", "Dark")}</span>
          </div>
        </SelectItem>
        <SelectItem value="gray">
          <div className="flex items-center gap-2">
            <Palette className="h-4 w-4" aria-hidden="true" />
            <span>{t("settings.theme_gray", "Gray")}</span>
          </div>
        </SelectItem>
        <SelectItem value="system">
          <div className="flex items-center gap-2">
            <Monitor className="h-4 w-4" aria-hidden="true" />
            <span>{t("settings.theme_system", "System")}</span>
          </div>
        </SelectItem>
      </SelectContent>
    </Select>
  )
}
