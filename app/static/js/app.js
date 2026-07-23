/* VitisGuard — helpers compartidos del frontend */
const VG = (() => {
  const api = (path, opts) =>
    fetch(path, opts).then((r) => {
      if (!r.ok) throw new Error(`${r.status} ${path}`);
      return r.json();
    });

  const fmtDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString("es-AR", {
      day: "2-digit", month: "2-digit", year: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  };

  const STATUS = {
    online:   { color: "#4c9a2a", label: "En línea" },
    offline:  { color: "#6c757d", label: "Sin reporte" },
    alert:    { color: "#dc3545", label: "Alerta" },
    inactive: { color: "#3a3546", label: "Inactivo" },
  };
  const statusInfo = (s) => STATUS[s] || STATUS.offline;

  const LEVEL_BADGE = { critical: "text-bg-danger", warning: "text-bg-warning", info: "text-bg-info" };
  const levelBadge = (lvl) => LEVEL_BADGE[lvl] || "text-bg-secondary";

  async function updateAlertBadge() {
    try {
      const alerts = await api("/api/alerts?open=true");
      const badge = document.getElementById("nav-alert-badge");
      if (!badge) return;
      if (alerts.length > 0) {
        badge.textContent = alerts.length;
        badge.classList.remove("d-none");
      } else {
        badge.classList.add("d-none");
      }
    } catch (_) { /* silencioso */ }
  }

  document.addEventListener("DOMContentLoaded", updateAlertBadge);

  return { api, fmtDate, statusInfo, levelBadge, updateAlertBadge };
})();
