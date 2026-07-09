import express from "express";
import request from "supertest";

// The triage route imports the rate-limit middleware, which pulls in Redis.
// Stub it so the router can mount without that dependency.
jest.mock("../src/middleware/rateLimit", () => ({
    triageLimiter: (_req: unknown, _res: unknown, next: () => void) => next(),
    limiter: (_req: unknown, _res: unknown, next: () => void) => next(),
    reportLimiter: (_req: unknown, _res: unknown, next: () => void) => next(),
}));

// Keep the real Zod request schemas, urgency classifier, and disclaimer; only
// control what the RAG lookup returns so we can drive valid vs malformed output.
const mockRetrieve = jest.fn();
jest.mock("../src/services/medicineRag.service", () => {
    const actual = jest.requireActual("../src/services/medicineRag.service");
    return {
        ...actual,
        retrieveRelevantMedicines: (...args: unknown[]) => mockRetrieve(...args),
    };
});

import triageRouter from "../src/routes/triage";

function buildApp() {
    const app = express();
    app.use(express.json());
    app.use("/api/triage", triageRouter);
    return app;
}

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

// generic_name is required by the schema; dropping it models a bad upstream row.
const malformedMedicine = { ...validMedicine } as Record<string, unknown>;
delete malformedMedicine.generic_name;

describe("triage routes response validation", () => {
    const app = buildApp();

    beforeEach(() => {
        jest.clearAllMocks();
    });

    describe("POST /api/triage/medicine-query", () => {
        it("returns 200 and passes a well-formed response through unchanged", async () => {
            mockRetrieve.mockResolvedValue([validMedicine]);

            const res = await request(app)
                .post("/api/triage/medicine-query")
                .send({ query: "fever" });

            expect(res.status).toBe(200);
            expect(res.body.query).toBe("fever");
            expect(res.body.medicines).toEqual([validMedicine]);
            expect(typeof res.body.disclaimer).toBe("string");
        });

        it("returns 502 when the RAG service yields a malformed medicine", async () => {
            mockRetrieve.mockResolvedValue([malformedMedicine]);

            const res = await request(app)
                .post("/api/triage/medicine-query")
                .send({ query: "fever" });

            expect(res.status).toBe(502);
            expect(res.body).toEqual({
                error: "Triage service produced an invalid response.",
            });
        });

        it("returns 400 on an invalid request body (real Zod schema still runs)", async () => {
            const res = await request(app).post("/api/triage/medicine-query").send({});

            expect(res.status).toBe(400);
            expect(mockRetrieve).not.toHaveBeenCalled();
        });
    });

    describe("POST /api/triage/recommend", () => {
        it("returns 200 with a valid response and no coordinates", async () => {
            mockRetrieve.mockResolvedValue([validMedicine]);

            const res = await request(app)
                .post("/api/triage/recommend")
                .send({ symptoms: "mild fever and headache" });

            expect(res.status).toBe(200);
            expect(res.body.emergency).toBe(false);
            expect(res.body.pharmacies).toEqual([]);
            expect(res.body.medicines).toEqual([validMedicine]);
        });

        it("flags an emergency for urgent symptoms", async () => {
            mockRetrieve.mockResolvedValue([validMedicine]);

            const res = await request(app)
                .post("/api/triage/recommend")
                .send({ symptoms: "chest pain since morning" });

            expect(res.status).toBe(200);
            expect(res.body.emergency).toBe(true);
            expect(res.body.urgentKeywords).toContain("chest pain");
        });

        it("returns 502 when the RAG service yields a malformed medicine", async () => {
            mockRetrieve.mockResolvedValue([malformedMedicine]);

            const res = await request(app)
                .post("/api/triage/recommend")
                .send({ symptoms: "mild fever and headache" });

            expect(res.status).toBe(502);
            expect(res.body).toEqual({
                error: "Triage service produced an invalid response.",
            });
        });

        it("returns 400 on an invalid request body", async () => {
            const res = await request(app).post("/api/triage/recommend").send({});

            expect(res.status).toBe(400);
            expect(mockRetrieve).not.toHaveBeenCalled();
        });
    });
});
