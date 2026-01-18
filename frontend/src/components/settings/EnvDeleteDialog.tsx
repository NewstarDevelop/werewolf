/**
 * Environment Variable Delete Dialog
 * Confirmation dialog for deleting environment variables
 */

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface EnvDeleteDialogProps {
  open: boolean;
  variableName: string;
  onClose: () => void;
  onConfirm: () => void;
}

export function EnvDeleteDialog({ open, variableName, onClose, onConfirm }: EnvDeleteDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Environment Variable</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete <span className="font-mono font-semibold">{variableName}</span>?
            This action cannot be undone and will require a server restart to take effect.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
