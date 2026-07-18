const fun = require("funcaptcha");

const PKEY = "476068BF-9607-4799-B53D-966BE98E2B81";
const SURL = "https://roblox-api.arkoselabs.com";
const SITE = "https://www.roblox.com";

async function main() {
    const action = process.argv[2];

    if (action === "get_embed_url") {
        const blob = process.argv[3];
        if (!blob) {
            console.log(JSON.stringify({ error: "No blob provided" }));
            process.exit(1);
        }

        const result = await fun.getToken({
            pkey: PKEY,
            surl: SURL,
            data: { blob },
            site: SITE,
        });

        const session = new fun.Session(result.token);
        const embedUrl = session.getEmbedUrl();

        console.log(JSON.stringify({
            token: result.token,
            embed_url: embedUrl,
            challenge_url: result.challenge_url || "",
        }));
    }

    else if (action === "get_token") {
        const blob = process.argv[3];
        if (!blob) {
            console.log(JSON.stringify({ error: "No blob provided" }));
            process.exit(1);
        }

        const result = await fun.getToken({
            pkey: PKEY,
            surl: SURL,
            data: { blob },
            site: SITE,
        });

        console.log(JSON.stringify({
            token: result.token,
            challenge_url: result.challenge_url || "",
            sup: result.sup || "",
        }));
    }

    else {
        console.log(JSON.stringify({ error: "Unknown action: " + action }));
        process.exit(1);
    }
}

main().catch(err => {
    console.log(JSON.stringify({ error: err.message }));
    process.exit(1);
});
