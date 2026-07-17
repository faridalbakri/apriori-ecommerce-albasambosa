import { sleep } from "k6";
import http from "k6/http";
import { check } from "k6";

export const options = {
    scenarios: {
        mixed_load: {
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
        "http_req_duration{type:read}": ["p(95)<1000"],
        "http_req_duration{type:write}": ["p(95)<3000"],
        http_req_failed: ["rate<0.01"],
    },
    summaryTrendStats: ["min", "avg", "p(90)", "p(95)", "p(99)", "max"],
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

const PRODUCT_IDS = [13, 14, 15, 16, 17];

const STATIC_PAGES = [
    "/kebijakan-privasi",
    "/kebijakan-cookie",
    "/syarat-ketentuan",
];

function randomProductId() {
    return PRODUCT_IDS[Math.floor(Math.random() * PRODUCT_IDS.length)];
}

// 70% of VUs: browsing (read traffic)
function browse() {
    const pages = [
        // Catalog
        () =>
            http.get(`${BASE_URL}/menu`, {
                tags: { type: "read", endpoint: "catalog" },
            }),
        // Product detail
        () =>
            http.get(`${BASE_URL}/produk/${randomProductId()}`, {
                tags: { type: "read", endpoint: "product" },
            }),
        // Static page
        () =>
            http.get(
                `${BASE_URL}${STATIC_PAGES[Math.floor(Math.random() * STATIC_PAGES.length)]}`,
                { tags: { type: "read", endpoint: "static" } },
            ),
    ];

    const action = pages[Math.floor(Math.random() * pages.length)];
    const res = action();

    check(res, { "read: status 200": (r) => r.status === 200 });

    sleep(2 + Math.random() * 4);
}

// 30% of VUs: cart + checkout (write traffic)
function write() {
    // Step 1: View a product first (adding to cart requires product page)
    const productRes = http.get(`${BASE_URL}/produk/${randomProductId()}`, {
        tags: { type: "write", endpoint: "product_view" },
    });
    check(productRes, { "write product: status 200": (r) => r.status === 200 });

    sleep(0.5 + Math.random());

    // Step 2: View cart
    const cartRes = http.get(`${BASE_URL}/keranjang`, {
        tags: { type: "write", endpoint: "cart" },
    });
    check(cartRes, { "write cart: status 200": (r) => r.status === 200 });

    sleep(0.5 + Math.random());

    // Step 3: 50% of write users proceed to checkout page
    if (Math.random() > 0.5) {
        const checkoutRes = http.get(`${BASE_URL}/checkout`, {
            tags: { type: "write", endpoint: "checkout" },
        });
        check(checkoutRes, {
            "write checkout: status 200": (r) => r.status === 200,
        });
    }

    // Step 4: Occasionally check order tracking page
    if (Math.random() > 0.7) {
        const trackRes = http.get(`${BASE_URL}/cek-status`, {
            tags: { type: "write", endpoint: "tracking" },
        });
        check(trackRes, {
            "write tracking: status 200": (r) => r.status === 200,
        });
    }

    sleep(1 + Math.random() * 3);
}

export default function () {
    // 70/30 split based on VU ID (deterministic, stable distribution)
    const isRead = __VU <= 35; // 35 out of 50 VUs = 70%

    if (isRead) {
        browse();
    } else {
        write();
    }
}
