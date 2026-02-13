import { useState, useEffect, useRef, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Loader2, TrendingUp, Trophy, AlertCircle, AlertTriangle, Copy, CheckCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from 'react-markdown';
import { toast } from "sonner";
import { API_BASE_URL } from "@/services/api";
import { getAuthHeader } from "@/utils/token";

interface GameAnalysisDialogProps {
  gameId: string;
  isOpen: boolean;
  onClose: () => void;
}

interface AnalysisData {
  game_id: string;
  winner: string;
  total_days: number;
  analysis: string;
  game_summary: {
    total_players: number;
    alive_players: number;
    total_days: number;
    total_speeches: number;
    total_votes: number;
    winner: string;
  };
}

const GameAnalysisDialog = ({ gameId, isOpen, onClose }: GameAnalysisDialogProps) => {
  const { t } = useTranslation(['common', 'game']);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const fetchedGameIdRef = useRef<string | null>(null); // Track which game we've fetched for

  // Debug mode (only enabled in development)
  const DEBUG = import.meta.env.DEV;

  // Fetch analysis when dialog opens
  const fetchAnalysis = useCallback(async () => {
    if (DEBUG) console.log('[GameAnalysisDialog] Starting fetch for game:', gameId);
    setIsLoading(true);
    setError(null);

    try {
      const url = `${API_BASE_URL}/api/game/${gameId}/analyze`;
      if (DEBUG) console.log('[GameAnalysisDialog] Fetching:', url);

      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader()
        }
      });
      if (DEBUG) console.log('[GameAnalysisDialog] Response status:', response.status);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        if (DEBUG) console.error('[GameAnalysisDialog] API error:', errorData);
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data: AnalysisData = await response.json();
      if (DEBUG) console.log('[GameAnalysisDialog] Analysis data received:', data);
      setAnalysis(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      if (DEBUG) console.error('[GameAnalysisDialog] Fetch error:', err);
      setError(errorMessage);
    } finally {
      setIsLoading(false);
      if (DEBUG) console.log('[GameAnalysisDialog] Fetch complete');
    }
  }, [gameId, DEBUG]);

  // 🔧 FIX: Use useEffect to watch isOpen and gameId changes
  // This ensures the request is sent when the dialog is opened externally or gameId changes
  useEffect(() => {
    if (DEBUG) console.log('[GameAnalysisDialog] State changed - isOpen:', isOpen, 'gameId:', gameId);

    if (isOpen) {
      // Fetch if we haven't fetched for this specific gameId yet
      if (fetchedGameIdRef.current !== gameId && !isLoading) {
        if (DEBUG) console.log('[GameAnalysisDialog] Triggering fetchAnalysis...');
        fetchedGameIdRef.current = gameId; // Mark as fetched for this game
        fetchAnalysis();
      }
    } else {
      // Reset state when dialog closes
      if (DEBUG) console.log('[GameAnalysisDialog] Resetting state on close');
      setAnalysis(null);
      setError(null);
      fetchedGameIdRef.current = null; // Reset fetch tracker
    }
  }, [isOpen, gameId, fetchAnalysis, isLoading, DEBUG]);

  // Handle dialog close action
  const handleOpenChange = (open: boolean) => {
    if (DEBUG) console.log('[GameAnalysisDialog] Dialog close triggered');
    if (!open) {
      onClose();
    }
  };

  // Copy configuration to clipboard
  const handleCopyConfig = () => {
    const configText = `OPENAI_API_KEY=your-api-key-here
ANALYSIS_PROVIDER=openai
ANALYSIS_MODEL=gpt-4o`;

    navigator.clipboard.writeText(configText).then(() => {
      setCopied(true);
      toast.success(t('game:analysis.config_copied'));
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      toast.error(t('game:analysis.copy_failed'));
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl h-[90vh] p-0 bg-card border-border">
        <DialogHeader className="px-6 py-4 border-b border-border bg-muted/30">
          <DialogTitle className="flex items-center gap-2 text-xl font-display">
            <TrendingUp className="w-5 h-5 text-accent" />
            {t('common:ui.game_analysis')}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-hidden">
          {isLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <Loader2 className="w-12 h-12 animate-spin text-accent" />
              <p className="text-muted-foreground text-lg">
                {t('game:analysis.generating')}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('game:analysis.may_take_time')}
              </p>
            </div>
          )}

          {error && (
            <div className="flex flex-col items-center justify-center h-full gap-4 px-6">
              <AlertCircle className="w-12 h-12 text-destructive" />
              <p className="text-destructive font-medium">{t('common:ui.analysis_failed')}</p>
              <p className="text-sm text-muted-foreground">{error}</p>
              <Button onClick={fetchAnalysis} variant="outline">
                {t('common:ui.retry')}
              </Button>
            </div>
          )}

          {analysis && !isLoading && (
            <ScrollArea className="h-full px-6 py-4">
              {/* Fallback Mode Warning */}
              {(() => {
                const isFallbackMode = analysis.analysis.includes("备用模式") ||
                                       analysis.analysis.includes("Fallback Mode") ||
                                       analysis.analysis.includes("暂时不可用");

                return isFallbackMode && (
                  <Alert variant="warning" className="mb-4 border-yellow-500/50 bg-yellow-500/10">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle className="text-lg font-semibold">{t('game:analysis.fallback_mode')}</AlertTitle>
                    <AlertDescription className="space-y-3">
                      <p className="text-sm">{t('game:analysis.fallback_hint')}</p>

                      {/* Configuration Steps */}
                      <div className="space-y-2">
                        <p className="text-sm font-medium">
                          {t('game:analysis.config_steps')}
                        </p>
                        <ol className="text-xs space-y-1 list-decimal list-inside text-muted-foreground">
                          <li>{t('game:analysis.config_step1')}</li>
                          <li>{t('game:analysis.config_step2')}</li>
                          <li>{t('game:analysis.config_step3')}</li>
                        </ol>
                      </div>

                      {/* Configuration Template */}
                      <div className="relative">
                        <code className="text-xs bg-muted/50 p-3 rounded block border border-border">
                          OPENAI_API_KEY=your-api-key-here<br />
                          ANALYSIS_PROVIDER=openai<br />
                          ANALYSIS_MODEL=gpt-4o
                        </code>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="absolute top-2 right-2 h-6 w-6 p-0"
                          onClick={handleCopyConfig}
                          aria-label={t('game:analysis.copy_config')}
                        >
                          {copied ? (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </Button>
                      </div>

                      {/* File Path Hint */}
                      <p className="text-xs text-muted-foreground">
                        {t('game:analysis.file_path')}
                        <code className="bg-muted/50 px-1 py-0.5 rounded">.env</code>
                        <span className="ml-1 text-muted-foreground/60">
                          {t('game:analysis.project_root')}
                        </span>
                      </p>

                      {/* Verification Command */}
                      <div className="bg-muted/30 p-2 rounded border border-border">
                        <p className="text-xs font-medium mb-1">
                          {t('game:analysis.verify_config')}
                        </p>
                        <code className="text-xs text-muted-foreground">
                          cd backend && python verify_config.py
                        </code>
                      </div>
                    </AlertDescription>
                  </Alert>
                );
              })()}

              {/* Game Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <SummaryCard
                  icon={<Trophy className="w-4 h-4" />}
                  label={t('game:game_over.winner_announce', { winner: analysis.winner })}
                  value=""
                  highlight
                />
                <SummaryCard
                  label={t('common:ui.total_days')}
                  value={analysis.total_days.toString()}
                />
                <SummaryCard
                  label={t('common:ui.total_speeches')}
                  value={analysis.game_summary.total_speeches.toString()}
                />
                <SummaryCard
                  label={t('common:ui.total_votes')}
                  value={analysis.game_summary.total_votes.toString()}
                />
              </div>

              {/* AI Analysis Content */}
              <div className="prose prose-invert max-w-none">
                <div className="bg-background/50 rounded-lg p-6 border border-border">
                  <ReactMarkdown
                    className="markdown-content"
                    components={{
                      h1: ({ ...props }) => (
                        <h1 className="text-2xl font-bold mb-4 text-foreground" {...props} />
                      ),
                      h2: ({ ...props }) => (
                        <h2 className="text-xl font-semibold mt-6 mb-3 text-foreground" {...props} />
                      ),
                      h3: ({ ...props }) => (
                        <h3 className="text-lg font-medium mt-4 mb-2 text-foreground" {...props} />
                      ),
                      p: ({ ...props }) => (
                        <p className="mb-3 text-muted-foreground leading-relaxed" {...props} />
                      ),
                      ul: ({ ...props }) => (
                        <ul className="list-disc list-inside mb-3 space-y-1" {...props} />
                      ),
                      ol: ({ ...props }) => (
                        <ol className="list-decimal list-inside mb-3 space-y-1" {...props} />
                      ),
                      li: ({ ...props }) => (
                        <li className="text-muted-foreground" {...props} />
                      ),
                      strong: ({ ...props }) => (
                        <strong className="font-semibold text-foreground" {...props} />
                      ),
                      code: ({ ...props }) => (
                        <code className="bg-muted px-1.5 py-0.5 rounded text-sm" {...props} />
                      ),
                      blockquote: ({ ...props }) => (
                        <blockquote className="border-l-4 border-accent pl-4 italic text-muted-foreground" {...props} />
                      ),
                      // 安全：仅允许 http/https 协议，防止 javascript: 等恶意链接
                      a: ({ href, children, ...props }) => {
                        const isAllowed = href && /^https?:\/\//i.test(href);
                        if (!isAllowed) {
                          return <span className="text-muted-foreground">{children}</span>;
                        }
                        return (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-accent underline hover:text-accent/80"
                            {...props}
                          >
                            {children}
                          </a>
                        );
                      },
                    }}
                  >
                    {analysis.analysis}
                  </ReactMarkdown>
                </div>
              </div>
            </ScrollArea>
          )}

          {!isLoading && !error && !analysis && (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <AlertCircle className="w-12 h-12 text-muted-foreground" />
              <p className="text-muted-foreground">
                {t('common:ui.analyzing')}
              </p>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-border bg-muted/30">
          <Button
            onClick={() => onClose()}
            className="w-full"
            variant="outline"
          >
            {t('common:app.close')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

interface SummaryCardProps {
  icon?: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}

const SummaryCard = ({ icon, label, value, highlight }: SummaryCardProps) => {
  return (
    <div
      className={`flex flex-col gap-2 p-4 rounded-lg border ${
        highlight
          ? 'bg-accent/10 border-accent/30'
          : 'bg-muted/30 border-border'
      }`}
    >
      {icon && <div className="text-accent">{icon}</div>}
      <p className="text-xs text-muted-foreground">{label}</p>
      {value && (
        <p className="text-lg font-bold text-foreground">{value}</p>
      )}
    </div>
  );
};

export default GameAnalysisDialog;
