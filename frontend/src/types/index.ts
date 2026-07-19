/**
 * Global TypeScript type definitions.
 *
 * These types are shared across the entire frontend application.
 * Domain-specific types belong in their respective module directories.
 */

/** Universally Unique Identifier — opaque string alias for UUID values. */
export type UUID = string;

/** A value that may be explicitly null. */
export type Nullable<T> = T | null;

/** A value that may be undefined (optional / not yet loaded). */
export type Optional<T> = T | undefined;
