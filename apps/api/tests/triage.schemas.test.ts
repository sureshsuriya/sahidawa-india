import {
    medicineMatchSchema,
    pharmacySchema,
    medicineQueryResponseSchema,
    recommendResponseSchema,
} from "../src/routes/triage.schemas";

const validMedicine = {
    id: "m-1",
    brand_name: "Crocin",
    generic_name: "Paracetamol",
    manufacturer: "GSK",
    composition: "Paracetamol 500mg",
    strength: "500mg",
    dosage_form: "tablet",
    schedule: null,
    mrp: 30,
    jan_aushadhi_price: 12,
    monograph: "Used for fever and pain.",
    similarity: 0.87,
};

const validPharmacy = {
    id: "p-1",
    name: "Jan Aushadhi Kendra",
    address: "MG Road",
    lat: 28.61,
    lng: 77.2,
    distance: "1.2 km",
    phone_number: null,
    is_verified: true,
    district: "New Delhi",
    state: "Delhi",
};

describe("triage response schemas", () => {
    it("accepts a well-formed medicine match", () => {
        expect(medicineMatchSchema.safeParse(validMedicine).success).toBe(true);
    });

    it("rejects a medicine missing the required generic_name", () => {
        const { generic_name, ...bad } = validMedicine;
        expect(medicineMatchSchema.safeParse(bad).success).toBe(false);
    });

    it("rejects a medicine whose mrp is a string instead of number|null", () => {
        expect(medicineMatchSchema.safeParse({ ...validMedicine, mrp: "cheap" }).success).toBe(
            false
        );
    });

    it("accepts a pharmacy without an id (id is optional)", () => {
        const { id, ...noId } = validPharmacy;
        expect(pharmacySchema.safeParse(noId).success).toBe(true);
    });

    it("rejects a pharmacy with non-numeric coordinates", () => {
        expect(pharmacySchema.safeParse({ ...validPharmacy, lat: "28.61" }).success).toBe(false);
    });

    it("accepts a valid /medicine-query response", () => {
        const res = medicineQueryResponseSchema.safeParse({
            query: "fever",
            medicines: [validMedicine],
            disclaimer: "Not medical advice.",
        });
        expect(res.success).toBe(true);
    });

    it("rejects a /medicine-query response with a malformed medicine in the array", () => {
        const res = medicineQueryResponseSchema.safeParse({
            query: "fever",
            medicines: [{ ...validMedicine, id: 123 }],
            disclaimer: "Not medical advice.",
        });
        expect(res.success).toBe(false);
    });

    it("accepts a valid /recommend response", () => {
        const res = recommendResponseSchema.safeParse({
            symptoms: "fever and headache",
            emergency: false,
            urgentKeywords: [],
            medicines: [validMedicine],
            pharmacies: [validPharmacy],
            disclaimer: "Not medical advice.",
        });
        expect(res.success).toBe(true);
    });

    it("rejects a /recommend response missing the emergency flag", () => {
        const res = recommendResponseSchema.safeParse({
            symptoms: "fever",
            urgentKeywords: [],
            medicines: [],
            pharmacies: [],
            disclaimer: "Not medical advice.",
        });
        expect(res.success).toBe(false);
    });
});
