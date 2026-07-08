import { recommendSchema } from "../src/services/medicineRag.service";
import {
    PHARMACY_SEARCH_RADIUS_DEFAULT_KM,
    PHARMACY_SEARCH_RADIUS_MIN_KM,
    PHARMACY_SEARCH_RADIUS_MAX_KM,
} from "@sahidawa/shared";

describe("shared pharmacy-radius constants", () => {
    it("exposes the expected bounds", () => {
        expect(PHARMACY_SEARCH_RADIUS_DEFAULT_KM).toBe(50);
        expect(PHARMACY_SEARCH_RADIUS_MIN_KM).toBe(1);
        expect(PHARMACY_SEARCH_RADIUS_MAX_KM).toBe(200);
    });

    it("applies the shared default radius when omitted", () => {
        const parsed = recommendSchema.parse({ symptoms: "fever" });
        expect(parsed.radius).toBe(PHARMACY_SEARCH_RADIUS_DEFAULT_KM);
    });

    it("rejects a radius above the shared maximum", () => {
        const result = recommendSchema.safeParse({
            symptoms: "fever",
            radius: PHARMACY_SEARCH_RADIUS_MAX_KM + 1,
        });
        expect(result.success).toBe(false);
    });

    it("rejects a radius below the shared minimum", () => {
        const result = recommendSchema.safeParse({
            symptoms: "fever",
            radius: PHARMACY_SEARCH_RADIUS_MIN_KM - 1,
        });
        expect(result.success).toBe(false);
    });
});
