console.log("[TestSW] Service Worker started!");
self.addEventListener("fetch", (e) => {
  console.log("[TestSW] Fetch:", e.request.url);
});
self.addEventListener("message", (e) => {
  console.log("[TestSW] Message from content script:", e.data);
});
