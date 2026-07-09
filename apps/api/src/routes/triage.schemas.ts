import { z } from "zod";

/**
 * Response contracts for the triage routes.
 *
 * The triage endpoints assemble their responses from several sources (the RAG
 * medicine service, the urgency classifier, and the pharmacy PostGIS RPC).
 * Validating the assembled payload against these schemas before it is sent
 * guarantees the client never receives an off-contract body — if an upstream
 * source returns something unexpected, the route returns a 502 instead of
 * forwarding malformed data.
 */

/** A single medicine suggestion, mirroring `MedicineMatch`. */
export const medicineMatchSchema = z.object({
    id: z.string(),
    brand_name: z.string().nullable(),
    generic_name: z.string(),
    manufacturer: z.string().nullable(),
    composition: z.string().nullable(),
    strength: z.string().nullable(),
    dosage_form: z.string().nullable(),
    schedule: z.string().nullable(),
    mrp: z.number().nullable(),
    jan_aushadhi_price: z.number().nullable(),
    monograph: z.string(),
    similarity: z.number().nullable(),
});

/** A formatted pharmacy result, mirroring the output of `formatPharmacy`. */
export const pharmacySchema = z.object({
    id: z.string().optional(),
    name: z.string(),
    address: z.string(),
    lat: z.number(),
    lng: z.number(),
    distance: z.string(),
    phone_number: z.string().nullable(),
    is_verified: z.boolean(),
    district: z.string().nullable(),
    state: z.string().nullable(),
});

/** Response body of `POST /api/triage/medicine-query`. */
export const medicineQueryResponseSchema = z.object({
    query: z.string(),
    medicines: z.array(medicineMatchSchema),
    disclaimer: z.string(),
});

/** Response body of `POST /api/triage/recommend`. */
export const recommendResponseSchema = z.object({
    symptoms: z.string(),
    emergency: z.boolean(),
    urgentKeywords: z.array(z.string()),
    medicines: z.array(medicineMatchSchema),
    pharmacies: z.array(pharmacySchema),
    disclaimer: z.string(),
});

export type MedicineQueryResponse = z.infer<typeof medicineQueryResponseSchema>;
export type RecommendResponse = z.infer<typeof recommendResponseSchema>;
