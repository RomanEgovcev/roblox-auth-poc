console.log("[TestCS] Content script running!");
chrome.runtime.sendMessage({type: "test", data: "hello from content script"})
  .then(r => console.log("[TestCS] Response:", r))
  .catch(e => console.log("[TestCS] Error sending message:", e.message));
