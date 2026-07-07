import express from "express";
import request from "supertest";
import medicineRouter from "../src/routes/medicine";

jest.mock("../src/db/client", () => ({
    supabase: {
        from: jest.fn().mockReturnThis(),
        select: jest.fn().mockReturnThis(),
        or: jest.fn().mockReturnThis(),
        limit: jest.fn().mockReturnThis(),
    },
}));

jest.mock("../src/utils/redis", () => ({
    redisClient: {
        setEx: jest.fn(),
    },
}));

function buildApp() {
    const app = express();
    app.use("/api/medicine", medicineRouter);
    return app;
}

describe("GET /api/medicine/languages", () => {
    const app = buildApp();

    it("should return Cache-Control header", async () => {
        // ML_SERVICE_URL is unset in the test env, so the handler short-circuits
        // with 503 before ever reaching the ML service — but cacheMiddleware
        // runs upstream of that check.
        const response = await request(app).get("/api/medicine/languages");

        expect(response.headers["cache-control"]).toContain("public");
    });
});
