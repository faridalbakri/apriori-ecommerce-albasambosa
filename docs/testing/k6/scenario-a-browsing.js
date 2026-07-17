import { sleep } from "k6";
import http from "k6/http";
import { check } from "k6";

export const options = {
    scenarios: {
        browsing: {
            executor: "ramping-vus",
            startVUs: 0,
            stages: [
                { duration: "30s", target: 50 }, // ramp-up
                { duration: "2m", target: 50 }, // steady state
                { duration: "30s", target: 0 }, // ramp-down
            ],
        },
    },
    thresholds: {
        "http_req_duration{endpoint:catalog}": ["p(95)<500"],
        "http_req_duration{endpoint:product}": ["p(95)<500"],
        http_req_failed: ["rate<0.01"],
    },
    summaryTrendStats: ["min", "avg", "p(90)", "p(95)", "p(99)", "max"],
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Product IDs from seeded database — update if products change
const PRODUCT_IDS = [13, 14, 15, 16, 17];

function randomProductId() {
    return PRODUCT_IDS[Math.floor(Math.random() * PRODUCT_IDS.length)];
}

export default function () {
    // Step 1: Browse catalog
    const catalogRes = http.get(`${BASE_URL}/menu`, {
        tags: { endpoint: "catalog" },
    });

    check(catalogRes, {
        "catalog: status 200": (r) => r.status === 200,
        "catalog: has products": (r) => r.body.includes("produk"),
    });

    // Simulate reading time (2-5 seconds)
    sleep(2 + Math.random() * 3);

    // Step 2: View 1-2 product detail pages
    const pagesToView = Math.random() > 0.5 ? 2 : 1;

    for (let i = 0; i < pagesToView; i++) {
        const productId = randomProductId();
        const productRes = http.get(`${BASE_URL}/produk/${productId}`, {
            tags: { endpoint: "product" },
        });

        check(productRes, {
            [`product ${productId}: status 200`]: (r) => r.status === 200,
        });

        sleep(1 + Math.random() * 3);
    }
}
