/* 原型交互：只做演示所需的轻量切换，不含业务逻辑 */
(function () {
  "use strict";

  // 通用分组切换：data-toggle-group="name" + data-toggle="value"
  document.querySelectorAll("[data-toggle-group]").forEach(function (group) {
    var name = group.getAttribute("data-toggle-group");
    group.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-toggle]");
      if (!btn || !group.contains(btn)) return;
      group.querySelectorAll("[data-toggle]").forEach(function (el) {
        el.classList.toggle("active", el === btn);
      });
      var value = btn.getAttribute("data-toggle");
      document.querySelectorAll('[data-panel-group="' + name + '"]').forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-panel") !== value;
      });
    });
  });

  // 点击图片缩略图，切换主图状态（仅视觉）
  document.querySelectorAll("[data-thumb]").forEach(function (thumb) {
    thumb.addEventListener("click", function () {
      var list = thumb.parentElement.querySelectorAll("[data-thumb]");
      list.forEach(function (el) {
        el.style.outline = el === thumb ? "2px solid var(--brand)" : "0";
        el.style.outlineOffset = "1px";
      });
    });
  });

  // 驳回弹层
  var rejectBtn = document.querySelector("[data-open-reject]");
  var rejectMask = document.querySelector("[data-reject-mask]");
  if (rejectBtn && rejectMask) {
    rejectBtn.addEventListener("click", function () { rejectMask.hidden = false; });
    rejectMask.addEventListener("click", function (e) {
      if (e.target === rejectMask || e.target.closest("[data-close-reject]")) {
        rejectMask.hidden = true;
      }
    });
  }
})();
