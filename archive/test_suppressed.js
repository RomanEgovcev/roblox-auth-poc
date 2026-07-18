const funcaptcha = require("./node_modules/funcaptcha/lib");
const undici = require("undici");
const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";

async function testRobloxLoginFlow() {
    // Step 1: Call Roblox login to get CSRF
    console.log("Getting CSRF token...");
    const res1 = await undici.request("https://auth.roblox.com/v2/login", { method: "POST" });
    const csrf = res1.headers["x-csrf-token"];
    console.log("CSRF:", csrf);

    // Step 2: Attempt login with fake creds to trigger captcha challenge
    console.log("\nTriggering captcha challenge...");
    const res2 = await undici.request("https://auth.roblox.com/v2/login", {
        method: "POST",
        headers: {
            "x-csrf-token": csrf,
            "content-type": "application/json",
            "user-agent": USER_AGENT
        },
        body: JSON.stringify({
            "ctype": "Username",
            "cvalue": "TestUser12345",
            "password": "TestPassword123!",
        })
    });

    console.log("Login response status:", res2.statusCode);
    const metadataHeader = res2.headers["rblx-challenge-metadata"];
    
    if (!metadataHeader) {
        console.log("No captcha challenge returned.");
        console.log("All response headers:");
        for (const [k, v] of Object.entries(res2.headers)) {
            console.log(`  ${k}: ${v}`);
        }
        const body = await res2.body.text();
        console.log("Response body:", body.substring(0, 500));
        return;
    }

    const fieldData = JSON.parse(Buffer.from(metadataHeader, "base64").toString());
    console.log("Challenge blob:", fieldData.dataExchangeBlob ? fieldData.dataExchangeBlob.substring(0, 50) + "..." : "none");

    if (!fieldData.dataExchangeBlob) {
        console.log("No dataExchangeBlob in challenge metadata");
        return;
    }

    // Step 3: Get Arkose token with the blob
    console.log("\nGetting Arkose token...");
    const token = await funcaptcha.getToken({
        pkey: "476068BF-9607-4799-B53D-966BE98E2B81",
        surl: "https://roblox-api.arkoselabs.com",
        data: {
            "blob": fieldData.dataExchangeBlob,
        },
        headers: {
            "User-Agent": USER_AGENT,
        },
        site: "https://www.roblox.com/login",
    });

    console.log("Token raw:", token.token ? token.token.substring(0, 100) + "..." : "no token");
    console.log("Full token response:", JSON.stringify(token, null, 2));
    
    // Check suppressed
    if (token.token && token.token.includes("sup=1")) {
        console.log("\n*** SUPPRESSED CAPTCHA! Token is valid immediately! ***");
    } else if (token.token && token.token.includes("sup=")) {
        console.log("\n*** NOT suppressed — need to solve challenges ***");
    } else {
        console.log("\n*** Could not determine suppressed status ***");
    }

    // Create session and get challenge to see game type
    if (token.token) {
        console.log("\nCreating session...");
        let session = new funcaptcha.Session(token, { userAgent: USER_AGENT });
        console.log("Token info:", JSON.stringify(session.tokenInfo, null, 2));
        
        try {
            let challenge = await session.getChallenge();
            console.log("Challenge game type:", challenge.gameType);
            console.log("Challenge variant:", challenge.variant);
            console.log("Challenge waves:", challenge.waves);
        } catch (err) {
            console.log("getChallenge error:", err.message);
        }
    }
}

// Also test without blob — direct getToken
async function testDirectToken() {
    console.log("\n\n=== Testing direct getToken (no blob) ===");
    try {
        const token = await funcaptcha.getToken({
            pkey: "476068BF-9607-4799-B53D-966BE98E2B81",
            surl: "https://roblox-api.arkoselabs.com",
            headers: { "User-Agent": USER_AGENT },
            site: "https://www.roblox.com/login",
        });
        console.log("Direct token response:", JSON.stringify(token, null, 2));
        if (token.token) {
            console.log("Token sup check:", token.token.includes("sup=1") ? "SUPPRESSED" : "not suppressed");
        }
    } catch (err) {
        console.log("Direct getToken error:", err.message);
    }
}

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

testRobloxLoginFlow().catch(console.error);
// testDirectToken().catch(console.error);
