// Album photo viewer: opens a photo in a dialog on this site, with previous/next,
// arrow keys and Escape. Without JavaScript, each photo still links to its image file.
(function () {
  var grid = document.querySelector("[data-lightbox]");
  var dialog = document.querySelector("dialog.lightbox");
  if (!grid || !dialog || typeof dialog.showModal !== "function") return;
  var links = Array.prototype.slice.call(grid.querySelectorAll("a"));
  var img = dialog.querySelector("img");
  var caption = dialog.querySelector("figcaption");
  var current = 0;

  function show(i) {
    current = (i + links.length) % links.length;
    var a = links[current];
    img.src = a.getAttribute("href");
    img.alt = a.querySelector("img").alt;
    caption.textContent = (a.dataset.caption ? a.dataset.caption + " · " : "") + (current + 1) + " of " + links.length;
  }
  links.forEach(function (a, i) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      show(i);
      dialog.showModal();
    });
  });
  dialog.querySelector(".lb-prev").addEventListener("click", function () { show(current - 1); });
  dialog.querySelector(".lb-next").addEventListener("click", function () { show(current + 1); });
  dialog.querySelector(".lb-close").addEventListener("click", function () { dialog.close(); });
  dialog.addEventListener("click", function (e) { if (e.target === dialog) dialog.close(); });
  dialog.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") show(current - 1);
    if (e.key === "ArrowRight") show(current + 1);
  });
})();
