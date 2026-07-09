import dns from "dns/promises";

/**
 * Hostname / IP-literal patterns that must never be the destination of a
 * server-side outbound request.
 *
 * `z.string().url()` only validates URL *format*, not where it points, so an
 * attacker could otherwise supply a cloud-metadata address (169.254.169.254),
 * a loopback address, or an internal service URL that gets fetched by the
 * server (SSRF). These cover loopback, the RFC 1918 private ranges,
 * link-local, and their IPv6 equivalents.
 */
export const BLOCKED_OUTBOUND_URL_PATTERNS = [
    /^localhost$/i,
    /^127\./,
    /^10\./,
    /^172\.(1[6-9]|2\d|3[01])\./,
    /^192\.168\./,
    /^169\.254\./,
    /^::1$/,
    /^fc00:/i,
    /^fe80:/i,
    /^::ffff:/i,
];

/**
 * Hard cap on how long a DNS lookup is allowed to take. Without this a slow or
 * malicious resolver could hang the request indefinitely (DoS). Configurable
 * via `DNS_LOOKUP_TIMEOUT_MS` so tests can shorten it.
 */
const DNS_TIMEOUT_MS = parseInt(process.env.DNS_LOOKUP_TIMEOUT_MS ?? "3000", 10);

function isBlockedHost(host: string): boolean {
    return BLOCKED_OUTBOUND_URL_PATTERNS.some((pattern) => pattern.test(host));
}

/**
 * Validates that `rawUrl` is safe to fetch from the server.
 *
 * Returns `true` only when the URL uses http(s), its hostname is not in a
 * blocked range, and the address it resolves to is also not in a blocked range
 * (so a public hostname that resolves to an internal IP is still rejected).
 * Any parse error, DNS failure, or DNS timeout resolves to `false` — the URL
 * is treated as unsafe by default.
 */
export async function validateOutboundUrl(rawUrl: string): Promise<boolean> {
    let timeoutHandle: NodeJS.Timeout | undefined;
    try {
        const { protocol, hostname } = new URL(rawUrl);
        if (protocol !== "https:" && protocol !== "http:") return false;

        // Strip the brackets around IPv6 literals (e.g. "[::1]" -> "::1").
        const normalizedHost = hostname.replace(/^\[|\]$/g, "");
        if (isBlockedHost(normalizedHost)) return false;

        // Race the DNS lookup against a hard timeout so a slow resolver can't
        // hang the request.
        const { address } = (await Promise.race([
            dns.lookup(normalizedHost),
            new Promise<never>((_, reject) => {
                timeoutHandle = setTimeout(
                    () => reject(new Error("DNS lookup timeout")),
                    DNS_TIMEOUT_MS
                );
            }),
        ])) as { address: string };

        if (isBlockedHost(address)) return false;

        return true;
    } catch {
        // Parse errors, DNS failures, and timeouts all mean "not verified safe".
        return false;
    } finally {
        if (timeoutHandle) clearTimeout(timeoutHandle);
    }
}
