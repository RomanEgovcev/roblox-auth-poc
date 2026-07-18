function FindProxyForURL(url, host) {
    if (dnsDomainIs(host, "nopecha.com")) {
        return "SOCKS5 127.0.0.1:10808";
    }
    return "DIRECT";
}
