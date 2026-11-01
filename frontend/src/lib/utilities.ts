import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combines class names with Tailwind CSS deduplication
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Formats timestamps into standard intelligence ISO/telemetry format
 */
export function formatTelemetryTimestamp(date: Date = new Date()): string {
  return date.toISOString().replace("T", " ").substring(0, 19) + " UTC";
}

/**
 * Copies text safely to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    console.error("Failed to copy text: ", err);
    return false;
  }
}
