/**
 * Date utility functions for handling server-side timestamps.
 */

/**
 * Parses a server-side timestamp string (UTC Naive) into a Date object.
 * Ensures the string is treated as UTC even if the browser would interpret it as local.
 * This is crucial because backend returns naive dates (no 'Z' or offset) which represent UTC,
 * but browsers default to Local Time for naive ISO strings.
 *
 * @param dateString - The date string from the backend (e.g. '2023-10-27T10:00:00')
 * @returns Date object or null if input is invalid/empty
 */
export function parseServerDate(dateString: string | null | undefined): Date | null {
  if (!dateString) return null;

  let date: Date;

  // If it already has timezone info (Z or +00:00), parse as is
  if (dateString.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(dateString)) {
    date = new Date(dateString);
  } else {
    // Treat as UTC by appending 'Z'
    date = new Date(`${dateString}Z`);
  }

  // Return null for invalid dates to prevent downstream crashes
  return isNaN(date.getTime()) ? null : date;
}
