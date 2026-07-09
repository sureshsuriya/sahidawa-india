/**
 * Cross-app numeric limits and thresholds shared between apps/web and apps/api.
 *
 * Centralizing these avoids client/server drift — e.g. a UI that allows
 * selecting more items than the API is willing to accept, which previously
 * happened with the interaction checker (frontend allowed 50, backend
 * enforced 20).
 */

/** Max number of medicines a user can select in the drug interaction checker. */
export const MAX_INTERACTION_MEDICINES = 50;

/** Max number of line items accepted per bulk pharmacy inventory upload request. */
export const MAX_BULK_UPLOAD_ITEMS = 500;

/** Max file size (in bytes) for bulk upload files. */
export const MAX_BULK_UPLOAD_FILE_SIZE_BYTES = 1 * 1024 * 1024; // 1MB

/**
 * Radius bounds (in km) for the "nearby pharmacies" geospatial search.
 *
 * Shared so the web client's default request radius stays in step with the
 * range the API's Zod schemas actually accept — previously both sides
 * hardcoded 50/1/200 independently.
 */
export const PHARMACY_SEARCH_RADIUS_DEFAULT_KM = 50;
export const PHARMACY_SEARCH_RADIUS_MIN_KM = 1;
export const PHARMACY_SEARCH_RADIUS_MAX_KM = 200;
