/**
 * Environment Variables Table
 * Displays list of environment variables with actions
 */

import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Edit, Trash2, Eye, EyeOff } from 'lucide-react';
import { EnvVariable } from '@/types/config';

interface EnvVariablesTableProps {
  variables: EnvVariable[];
  onEdit: (variable: EnvVariable) => void;
  onDelete: (variable: EnvVariable) => void;
}

export function EnvVariablesTable({ variables, onEdit, onDelete }: EnvVariablesTableProps) {
  const [visibleValues, setVisibleValues] = useState<Set<string>>(new Set());

  const toggleVisibility = (name: string) => {
    setVisibleValues(prev => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  if (variables.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No environment variables found. Click "Add Variable" to create one.
      </div>
    );
  }

  return (
    <div className="border rounded-md">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Variable Name</TableHead>
            <TableHead>Value</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {variables.map((variable) => {
            const isVisible = visibleValues.has(variable.name);
            const showValue = variable.is_sensitive ? (isVisible ? variable.value || '(empty)' : '********') : variable.value || '(empty)';

            return (
              <TableRow key={variable.name}>
                <TableCell className="font-mono font-semibold">
                  <div className="flex items-center gap-2">
                    {variable.name}
                    {variable.is_sensitive && (
                      <Badge variant="secondary" className="text-xs">
                        Sensitive
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm truncate max-w-md">
                      {showValue}
                    </span>
                    {variable.is_sensitive && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleVisibility(variable.name)}
                        className="h-6 w-6 p-0"
                      >
                        {isVisible ? (
                          <EyeOff className="h-3 w-3" />
                        ) : (
                          <Eye className="h-3 w-3" />
                        )}
                      </Button>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(variable)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onDelete(variable)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
