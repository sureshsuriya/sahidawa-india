import request from "supertest";
import express from "express";
import webhooksRouter from "../../src/routes/webhooks";
import { redisClient } from "../../src/utils/redis";

// Mock the redis client
jest.mock("../../src/utils/redis", () => ({
    redisClient: {
        isOpen: true,
        scan: jest.fn(),
        del: jest.fn(),
    },
}));

// Mock the rate limiter so tests don't fail due to too many requests
jest.mock("../../src/middleware/rateLimit", () => ({
    webhookLimiter: (req: any, res: any, next: any) => next(),
}));

// Mock logger to keep test output clean
jest.mock("../../src/utils/logger", () => ({
    __esModule: true,
    default: {
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
    },
}));

const app = express();
app.use(express.json());
app.use("/api/webhooks", webhooksRouter);

describe("Webhooks Routes", () => {
    beforeEach(() => {
        jest.clearAllMocks();
        process.env.SUPABASE_WEBHOOK_SECRET = "test-secret";
        (redisClient as any).isOpen = true;
    });

    describe("Authorization", () => {
        it("returns 401 when authorization header is missing", async () => {
            const res = await request(app).post("/api/webhooks/supabase/health-schemes").send({});

            expect(res.status).toBe(401);
            expect(res.body).toEqual({ error: "Unauthorized" });
        });

        it("returns 401 when authorization header is invalid", async () => {
            const res = await request(app)
                .post("/api/webhooks/supabase/health-schemes")
                .set("Authorization", "Bearer wrong-secret")
                .send({});

            expect(res.status).toBe(401);
            expect(res.body).toEqual({ error: "Unauthorized" });
        });
    });

    describe("POST /api/webhooks/supabase/health-schemes", () => {
        it("processes valid requests and deletes Redis keys", async () => {
            (redisClient.scan as jest.Mock).mockResolvedValueOnce({
                cursor: 0,
                keys: ["schemes:state:UP", "schemes:state:MH"],
            });

            const res = await request(app)
                .post("/api/webhooks/supabase/health-schemes")
                .set("Authorization", "Bearer test-secret")
                .send({});

            expect(res.status).toBe(200);
            expect(redisClient.scan).toHaveBeenCalledWith(0, {
                MATCH: "schemes:state:*",
                COUNT: 100,
            });
            expect(redisClient.del).toHaveBeenCalledWith(["schemes:state:UP", "schemes:state:MH"]);
            expect(res.body).toEqual({
                invalidated: 2,
                keys: ["schemes:state:UP", "schemes:state:MH"],
            });
        });

        it("handles missing cache keys without calling del", async () => {
            (redisClient.scan as jest.Mock).mockResolvedValueOnce({
                cursor: 0,
                keys: [],
            });

            const res = await request(app)
                .post("/api/webhooks/supabase/health-schemes")
                .set("Authorization", "Bearer test-secret")
                .send({});

            expect(res.status).toBe(200);
            expect(redisClient.del).not.toHaveBeenCalled();
        });

        it("safely handles disconnected Redis without crashing", async () => {
            (redisClient as any).isOpen = false;

            const res = await request(app)
                .post("/api/webhooks/supabase/health-schemes")
                .set("Authorization", "Bearer test-secret")
                .send({});

            expect(res.status).toBe(200);
            expect(res.body).toEqual({ invalidated: 0, message: "Redis unavailable" });
            expect(redisClient.scan).not.toHaveBeenCalled();
        });

        it("handles Redis scan errors safely", async () => {
            (redisClient.scan as jest.Mock).mockRejectedValueOnce(new Error("Redis error"));

            const res = await request(app)
                .post("/api/webhooks/supabase/health-schemes")
                .set("Authorization", "Bearer test-secret")
                .send({});

            expect(res.status).toBe(500);
            expect(res.body).toEqual({ error: "Cache invalidation failed" });
        });
    });

    describe("POST /api/webhooks/supabase/medicines", () => {
        it("invalidates drug lookup and voice search cache", async () => {
            (redisClient.scan as jest.Mock).mockResolvedValueOnce({
                cursor: 0,
                keys: ["drug:batch:B123:data"],
            });

            const res = await request(app)
                .post("/api/webhooks/supabase/medicines")
                .set("Authorization", "Bearer test-secret")
                .send({
                    record: {
                        batch_number: "B123",
                        brand_name: "Aspirin Plus",
                        generic_name: "Aspirin",
                    },
                });

            expect(res.status).toBe(200);
            expect(redisClient.scan).toHaveBeenCalledWith(0, {
                MATCH: "drug:batch:B123*",
                COUNT: 100,
            });
            expect(redisClient.del).toHaveBeenCalled();

            // The keys to delete should include the scanned batch keys and voice keys
            const deletedKeys = (redisClient.del as jest.Mock).mock.calls[0][0];
            expect(deletedKeys).toContain("drug:batch:B123:data");
            expect(deletedKeys).toContain("medicine:voice:aspirin_plus");
            expect(deletedKeys).toContain("medicine:voice:aspirin");
        });
    });

    describe("POST /api/webhooks/supabase/pharmacies (Async Invalidation)", () => {
        it("returns 200 immediately and dispatches async invalidation", async () => {
            (redisClient.scan as jest.Mock).mockResolvedValueOnce({
                cursor: 0,
                keys: ["pharmacy:123:details"],
            });

            const res = await request(app)
                .post("/api/webhooks/supabase/pharmacies")
                .set("Authorization", "Bearer test-secret")
                .send({
                    record: { id: "123" },
                });

            expect(res.status).toBe(200);
            expect(res.body).toEqual({
                success: true,
                message: "Invalidation event dispatched for pharmacies",
            });

            // Wait a tiny bit for the async promise to resolve
            await new Promise((resolve) => setTimeout(resolve, 10));

            expect(redisClient.scan).toHaveBeenCalledWith(0, {
                MATCH: "pharmacy:123*",
                COUNT: 100,
            });
            expect(redisClient.del).toHaveBeenCalledWith(["pharmacy:123:details"]);
        });
    });
});
