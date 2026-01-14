import { useTheme } from "next-themes";
import { Toaster as Sonner, toast } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

// Valid themes supported by sonner
const SONNER_THEMES = ["light", "dark", "system"] as const;
type SonnerTheme = (typeof SONNER_THEMES)[number];

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  // Map custom themes to sonner-compatible themes with validation
  const getSonnerTheme = (t: string): SonnerTheme => {
    if (t === "gray") return "light";
    if (SONNER_THEMES.includes(t as SonnerTheme)) return t as SonnerTheme;
    return "system"; // fallback for unknown themes
  };

  return (
    <Sonner
      theme={getSonnerTheme(theme)}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  );
};

export { Toaster, toast };
