import { sleep } from "k6";
import http from "k6/http";
import { check } from "k6";
import { SharedArray } from "k6/data";

export const options = {
    scenarios: {
        checkout_concurrent: {
            executor: "shared-iterations",
            vus: 10,
            iterations: 10,
            maxDuration: "60s",
            gracefulStop: "5s",
        },
    },
    thresholds: {
        "http_req_duration{endpoint:checkout_page}": ["p(95)<3000"],
        "http_req_duration{endpoint:product_page}": ["p(95)<1000"],
        http_req_failed: ["rate<0.01"],
    },
    summaryTrendStats: ["min", "avg", "p(90)", "p(95)", "p(99)", "max"],
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Product IDs from database
const PRODUCT_IDS = [13, 14, 15, 16, 17];
const SESSION_IDS = new SharedArray("sessions", function () {
    return Array.from({ length: 10 }, (_, i) => `k6-loadtest-session-${i + 1}`);
});

export default function () {
    const vuId = __VU - 1;
    const sessionId = SESSION_IDS[vuId % SESSION_IDS.length];

    // Set session cookie for guest cart
    const cookieHeaders = {
        headers: {
            Cookie: `laravel_session=${sessionId}`,
        },
    };

    // Step 1: View a product (warm-up, confirm cart state)
    const productId =
        PRODUCT_IDS[Math.floor(Math.random() * PRODUCT_IDS.length)];
    const productRes = http.get(`${BASE_URL}/produk/${productId}`, {
        ...cookieHeaders,
        tags: { endpoint: "product_page" },
    });

    check(productRes, {
        "product: status 200": (r) => r.status === 200,
    });

    sleep(1);

    // Step 2: Load checkout page (the key measurement)
    const checkoutRes = http.get(`${BASE_URL}/checkout`, {
        ...cookieHeaders,
        tags: { endpoint: "checkout_page" },
    });

    check(checkoutRes, {
        "checkout: status 200": (r) => r.status === 200,
        "checkout: has form": (r) =>
            r.body.includes("Buat Pesanan") ||
            r.body.includes("Keranjang masih kosong"),
    });

    // Step 3: Load cart page (verification)
    const cartRes = http.get(`${BASE_URL}/keranjang`, {
        ...cookieHeaders,
        tags: { endpoint: "cart_page" },
    });

    check(cartRes, {
        "cart: status 200": (r) => r.status === 200,
    });

    sleep(1);
}
