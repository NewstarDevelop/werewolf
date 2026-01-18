/**
 * Environment variable management types
 */

export interface EnvVariable {
  name: string;
  value: string | null;
  is_sensitive: boolean;
  is_set: boolean;
  source: 'env_file';
}

export interface EnvUpdateItem {
  name: string;
  action: 'set' | 'unset';
  value?: string;
  confirm_sensitive?: boolean;
}

export interface EnvUpdateRequest {
  updates: EnvUpdateItem[];
}

export interface EnvUpdateItemResult {
  name: string;
  action: 'set' | 'unset';
  status: 'created' | 'updated' | 'deleted' | 'skipped';
  message?: string;
}

export interface EnvUpdateResult {
  success: boolean;
  results: EnvUpdateItemResult[];
  restart_required: boolean;
  env_file_path: string;
}
