import jsPDF from "jspdf";
import html2canvas from "html2canvas";

const BRAND_BLUE  = [30, 64, 175];
const BRAND_LIGHT = [239, 246, 255];
const GREEN       = [22, 163, 74];
const YELLOW      = [202, 138, 4];
const RED         = [220, 38, 38];
const GRAY        = [107, 114, 128];
const DARK        = [17, 24, 39];

function riskColor(level) {
  if (!level) return GRAY;
  const l = level.toLowerCase();
  if (l === "low")    return GREEN;
  if (l === "medium") return YELLOW;
  if (l === "high")   return RED;
  return GRAY;
}

function fmt(val, decimals = 1) {
  if (val == null) return "N/A";
  if (typeof val === "number") return val.toFixed(decimals);
  return String(val);
}

function formatParamValue(v) {
  if (v == null) return "N/A";
  if (Array.isArray(v)) {
    return v.map((item, i) =>
      typeof item === "object"
        ? `[${i + 1}] ${Object.entries(item).map(([k, val]) => `${k}: ${val}`).join(", ")}`
        : String(item)
    ).join(" | ");
  }
  if (typeof v === "object") return Object.entries(v).map(([k, val]) => `${k}: ${val}`).join(", ");
  if (typeof v === "number") return v.toFixed(4);
  return String(v);
}

export async function downloadSimulationPDF(sim, chartRef) {
  const pdf   = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageW = pdf.internal.pageSize.getWidth();
  const pageH = pdf.internal.pageSize.getHeight();
  const margin = 14;
  const cW     = pageW - margin * 2;
  let y        = margin;

  // ── Helpers ───────────────────────────────────────────────────────────────
  const setColor = (arr, type = "text") => {
    if (type === "text") pdf.setTextColor(arr[0], arr[1], arr[2]);
    else                 pdf.setFillColor(arr[0], arr[1], arr[2]);
  };
  const resetColor = () => pdf.setTextColor(DARK[0], DARK[1], DARK[2]);

  const checkPage = (needed = 20) => {
    if (y + needed > pageH - margin) { pdf.addPage(); y = margin; }
  };

  const addKV = (label, value, unit = "") => {
    checkPage(8);
    pdf.setFontSize(10);
    pdf.setFont("helvetica", "bold");
    resetColor();
    pdf.text(`${label}: `, margin, y);
    const lw = pdf.getTextWidth(`${label}: `);
    pdf.setFont("helvetica", "normal");
    const display = `${value ?? "N/A"}${unit ? " " + unit : ""}`;
    const lines = pdf.splitTextToSize(display, cW - lw);
    pdf.text(lines, margin + lw, y);
    y += lines.length * 5 + 1;
  };

  const addSectionTitle = (title) => {
    checkPage(14);
    y += 5;
    setColor(BRAND_LIGHT, "fill");
    pdf.rect(margin, y - 5, cW, 8, "F");
    setColor(BRAND_BLUE, "fill");
    pdf.rect(margin, y - 5, 3, 8, "F");
    pdf.setFontSize(11);
    pdf.setFont("helvetica", "bold");
    setColor(BRAND_BLUE);
    pdf.text(title, margin + 6, y);
    resetColor();
    y += 6;
  };

  // ── Header ────────────────────────────────────────────────────────────────
  setColor(BRAND_BLUE, "fill");
  pdf.rect(0, 0, pageW, 28, "F");
  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(18);
  pdf.setFont("helvetica", "bold");
  pdf.text("PK Simulation Report", margin, 13);
  pdf.setFontSize(9);
  pdf.setFont("helvetica", "normal");
  pdf.text("Pharmacokinetic Analysis — Patient Copy", margin, 20);
  pdf.text(`Generated: ${new Date().toLocaleString()}`, pageW - margin, 20, { align: "right" });
  resetColor();
  y = 34;

  // Simulation meta row
  pdf.setFontSize(8);
  pdf.setFont("helvetica", "normal");
  setColor(GRAY);
  pdf.text(`Simulation ID: ${sim.id ?? "—"}`, margin, y);
  pdf.text(
    `Shared by: ${sim.shared_by ?? "—"}   |   Shared at: ${sim.shared_at ? new Date(sim.shared_at).toLocaleDateString() : "—"}`,
    pageW - margin, y, { align: "right" }
  );
  resetColor();
  y += 5;
  pdf.setDrawColor(220, 220, 220);
  pdf.line(margin, y, margin + cW, y);
  y += 5;

  // ── At-a-Glance Summary ───────────────────────────────────────────────────
  const te        = sim.therapeutic_eval ?? {};
  const tw        = sim.therapeutic_window ?? {};
  const pc        = sim.patient_context ?? {};
  const ade       = sim.ade_screening ?? {};
  const params    = sim.params_used ?? {};
  const pctWithin = typeof te.pct_within === "number" ? te.pct_within : null;
  const pctAbove  = typeof te.pct_above  === "number" ? te.pct_above  : null;
  const pctBelow  = typeof te.pct_below  === "number" ? te.pct_below  : null;
  const riskLevel = typeof te.ade_risk_level === "string" ? te.ade_risk_level : null;
  const alerts    = Array.isArray(te.alerts) ? te.alerts : [];

  // Card
  setColor(BRAND_LIGHT, "fill");
  pdf.rect(margin, y, cW, 32, "F");
  pdf.setDrawColor(...BRAND_BLUE);
  pdf.rect(margin, y, cW, 32, "S");
  y += 5;

  pdf.setFontSize(10);
  pdf.setFont("helvetica", "bold");
  setColor(BRAND_BLUE);
  pdf.text("At-a-Glance Summary", margin + 4, y);
  y += 7;

  // 3 stat columns — rounded to 1 decimal
  const cols = [
    { label: "Time in Range", value: pctWithin != null ? `${pctWithin.toFixed(1)}%` : "N/A", color: (pctWithin ?? 0) >= 70 ? GREEN : (pctWithin ?? 0) >= 50 ? YELLOW : RED },
    { label: "Time Too High", value: pctAbove  != null ? `${pctAbove.toFixed(1)}%`  : "N/A", color: (pctAbove  ?? 0) > 10  ? RED   : GREEN },
    { label: "Time Too Low",  value: pctBelow  != null ? `${pctBelow.toFixed(1)}%`  : "N/A", color: (pctBelow  ?? 0) > 20  ? RED   : GREEN },
  ];
  const colW = cW / 3;
  cols.forEach((col, i) => {
    const cx = margin + i * colW + colW / 2;
    pdf.setFontSize(16);
    pdf.setFont("helvetica", "bold");
    setColor(col.color);
    pdf.text(col.value, cx, y, { align: "center" });
    pdf.setFontSize(8);
    pdf.setFont("helvetica", "normal");
    setColor(GRAY);
    pdf.text(col.label, cx, y + 5, { align: "center" });
  });
  y += 13;

  // Risk badge + flags on same line
  const rc = riskColor(riskLevel);
  setColor(rc, "fill");
  pdf.roundedRect(margin + 4, y - 2, 48, 6, 2, 2, "F");
  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(8);
  pdf.setFont("helvetica", "bold");
  pdf.text(`Risk: ${riskLevel ? riskLevel.toUpperCase() : "UNKNOWN"}`, margin + 8, y + 2);

  if (sim.flag_too_high || sim.flag_too_low) {
    setColor(RED);
    pdf.setFontSize(8);
    const flagText = [
      sim.flag_too_high ? "⚠ TOO HIGH" : "",
      sim.flag_too_low  ? "⚠ TOO LOW"  : "",
    ].filter(Boolean).join("   ");
    pdf.text(flagText, margin + 58, y + 2);
  }
  resetColor();
  y += 10;

  // ── Medication & Dosing ───────────────────────────────────────────────────
  addSectionTitle("Medication & Dosing");
  addKV("Medication",          sim.medication_name || sim.medication_id);
  addKV("Dose",                fmt(sim.dose_mg, 0),      "mg");
  addKV("Dosing Interval",     fmt(sim.interval_hr, 0),  "hr");
  addKV("Simulation Duration", fmt(sim.duration_hr, 1),  "hr");

  // ── PK Metrics ────────────────────────────────────────────────────────────
  addSectionTitle("Pharmacokinetic Metrics");
  addKV("Cmax (Peak)",   fmt(sim.cmax_mg_l,  4), "mg/L");
  addKV("Cmin (Trough)", fmt(sim.cmin_mg_l,  4), "mg/L");
  addKV("AUC",           fmt(sim.auc_mg_h_l, 4), "mg·h/L");

  // Therapeutic window bar
  if (tw.lower_mg_l != null && tw.upper_mg_l != null) {
    y += 3;
    checkPage(28);
    pdf.setFontSize(9);
    pdf.setFont("helvetica", "bold");
    resetColor();
    pdf.text("Therapeutic Window:", margin, y);
    y += 5;
    const barW = cW, barH = 7;
    const lo = tw.lower_mg_l, hi = tw.upper_mg_l;
    const cmax = sim.cmax_mg_l ?? hi;
    const scale = barW / (hi * 1.5);
    pdf.setFillColor(225, 225, 225);
    pdf.rect(margin, y, barW, barH, "F");
    setColor(GREEN, "fill");
    pdf.rect(margin + lo * scale, y, (hi - lo) * scale, barH, "F");
    const cmaxX = Math.min(margin + cmax * scale, margin + barW - 1);
    setColor(RED, "fill");
    pdf.rect(cmaxX - 0.7, y - 1, 1.5, barH + 2, "F");
    pdf.setFontSize(7);
    setColor(GRAY);
    pdf.text(`${lo} mg/L`, margin + lo * scale, y + barH + 4);
    pdf.text(`${hi} mg/L`, margin + hi * scale, y + barH + 4);
    setColor(RED);
    pdf.text("▲ Cmax", cmaxX, y - 2, { align: "center" });
    setColor(GRAY);
    pdf.text(`Source: ${tw.source ?? "N/A"}`, margin, y + barH + 9);
    resetColor();
    y += barH + 14;
  }

  // ── Therapeutic Evaluation ────────────────────────────────────────────────
  addSectionTitle("Therapeutic Evaluation");
  Object.entries(te).forEach(([k, v]) => {
    if (k === "alerts") return;
    addKV(k, typeof v === "number" ? v.toFixed(3) : String(v ?? "N/A"));
  });

  // ── Alerts ────────────────────────────────────────────────────────────────
  if (alerts.length > 0) {
    addSectionTitle("What This Means For You");
    alerts.forEach((a) => {
      checkPage(10);
      setColor(RED, "fill");
      pdf.rect(margin, y - 3.5, 2.5, 5, "F");
      pdf.setFontSize(10);
      pdf.setFont("helvetica", "normal");
      resetColor();
      const lines = pdf.splitTextToSize(String(a), cW - 6);
      pdf.text(lines, margin + 5, y);
      y += lines.length * 5 + 2;
    });
  }

  // ── PK Parameters Used ────────────────────────────────────────────────────
  if (Object.keys(params).length > 0) {
    addSectionTitle("PK Parameters Used");
    Object.entries(params).forEach(([k, v]) => {
      addKV(k, formatParamValue(v));
    });
  }

  // ── Patient Context ───────────────────────────────────────────────────────
  addSectionTitle("Patient Context");
  const patientFields = [
    ["Age",                  pc.age,                         ""],
    ["Sex",                  pc.sex,                         ""],
    ["Weight",               pc.weight_kg,                   "kg"],
    ["Height",               pc.height_cm,                   "cm"],
    ["Serum Creatinine",     pc.serum_creatinine_mg_dl,      "mg/dL"],
    ["Creatinine Clearance", pc.creatinine_clearance_ml_min, "mL/min"],
    ["CKD Stage",            pc.ckd_stage,                   ""],
    ["Pregnant",             String(pc.is_pregnant ?? "N/A"),""],
    ["Pregnancy Trimester",  pc.pregnancy_trimester,         ""],
    ["Breastfeeding",        String(pc.is_breastfeeding ?? "N/A"), ""],
    ["Liver Disease",        pc.liver_disease_status,        ""],
    ["Albumin",              pc.albumin_g_dl,                "g/dL"],
    ["Systolic BP",          pc.systolic_bp_mm_hg,           "mmHg"],
    ["Diastolic BP",         pc.diastolic_bp_mm_hg,          "mmHg"],
    ["Heart Rate",           pc.heart_rate_bpm,              "bpm"],
  ];
  patientFields.forEach(([label, val, unit]) => {
    if (val == null || val === "N/A" || val === "null") return;
    addKV(label, val, unit);
  });
  if (pc.conditions?.length)          addKV("Conditions",          pc.conditions.join(", "));
  if (pc.current_medications?.length) addKV("Current Medications", pc.current_medications.join(", "));

  // ── ADE Screening ─────────────────────────────────────────────────────────
  if (Object.keys(ade).length > 0) {
    addSectionTitle("ADE / Drug Interaction Screening");
    Object.entries(ade).forEach(([k, v]) => {
      addKV(k, formatParamValue(v));
    });
  }

  // ── Chart ─────────────────────────────────────────────────────────────────
  if (chartRef?.current) {
    checkPage(90);
    addSectionTitle("Concentration–Time Profile");
    y += 2;
    try {
      const canvas  = await html2canvas(chartRef.current, { scale: 2, backgroundColor: "#ffffff", useCORS: true });
      const imgData = canvas.toDataURL("image/png");
      const imgH    = (canvas.height / canvas.width) * cW;
      checkPage(imgH + 5);
      pdf.addImage(imgData, "PNG", margin, y, cW, imgH);
      y += imgH + 5;
    } catch (err) {
      pdf.setFontSize(9); setColor(GRAY);
      pdf.text("(Chart could not be rendered)", margin, y);
      y += 6; resetColor();
    }
  }

  // ── Footer ────────────────────────────────────────────────────────────────
  const total = pdf.internal.getNumberOfPages();
  for (let i = 1; i <= total; i++) {
    pdf.setPage(i);
    setColor(BRAND_BLUE, "fill");
    pdf.rect(0, pageH - 12, pageW, 12, "F");
    pdf.setFontSize(8);
    pdf.setFont("helvetica", "normal");
    pdf.setTextColor(255, 255, 255);
    pdf.text(
      `Page ${i} of ${total}  |  Confidential – For clinical use only  |  Generated ${new Date().toLocaleDateString()}`,
      pageW / 2, pageH - 4.5, { align: "center" }
    );
  }

  pdf.save(`simulation_${sim.medication_name ?? sim.id ?? "report"}.pdf`);
}