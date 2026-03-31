import jsPDF from "jspdf";

import html2canvas from "html2canvas";

/**
 * Generates and downloads a PDF for a PK simulation result.
 *
 * @param {Object} sim         - The simulation object from your API response
 * @param {React.RefObject} chartRef - A ref attached to the chart DOM element
 */ 
export async function downloadSimulationPDF(sim, chartRef) {
  const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageW = pdf.internal.pageSize.getWidth();
  const margin = 14;
  const contentW = pageW - margin * 2;
  let y = margin;

  // ── Helpers ──────────────────────────────────────────────────────────────
  const addText = (text, size = 10, bold = false) => {
    pdf.setFontSize(size);
    pdf.setFont("helvetica", bold ? "bold" : "normal");
    const lines = pdf.splitTextToSize(String(text ?? "N/A"), contentW);
    pdf.text(lines, margin, y);
    y += lines.length * (size * 0.4) + 2;
  };

  const addSectionTitle = (title) => {
    y += 3;
    pdf.setFillColor(240, 240, 240);
    pdf.rect(margin, y - 4, contentW, 7, "F");
    addText(title, 11, true);
    y += 1;
  };

  const addKeyValue = (label, value, unit = "") => {
    pdf.setFontSize(10);
    pdf.setFont("helvetica", "bold");
    pdf.text(`${label}: `, margin, y);
    const labelWidth = pdf.getTextWidth(`${label}: `);
    pdf.setFont("helvetica", "normal");
    pdf.text(`${value ?? "N/A"}${unit ? " " + unit : ""}`, margin + labelWidth, y);
    y += 6;
  };

  const checkPageBreak = (neededHeight = 20) => {
    if (y + neededHeight > pdf.internal.pageSize.getHeight() - margin) {
      pdf.addPage();
      y = margin;
    }
  };

  // ── Header ────────────────────────────────────────────────────────────────
  pdf.setFillColor(30, 64, 175); // blue-800
  pdf.rect(0, 0, pageW, 22, "F");
  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(16);
  pdf.setFont("helvetica", "bold");
  pdf.text("PK Simulation Report", margin, 14);
  pdf.setTextColor(0, 0, 0);
  y = 30;

  // Date + Simulation ID
  pdf.setFontSize(9);
  pdf.setFont("helvetica", "normal");
  pdf.setTextColor(100, 100, 100);
  pdf.text(`Generated: ${new Date().toLocaleString()}`, margin, y);
  pdf.text(`Simulation ID: ${sim.id ?? "—"}`, pageW - margin, y, { align: "right" });
  pdf.setTextColor(0, 0, 0);
  y += 8;

  // ── Medication & Dose ────────────────────────────────────────────────────
  addSectionTitle("Medication & Dosing");
  addKeyValue("Medication ID", sim.medication_id);
  addKeyValue("Dose", sim.dose_mg, "mg");
  addKeyValue("Dosing Interval", sim.interval_hr, "hr");
  addKeyValue("Simulation Duration", sim.duration_hr, "hr");

  // ── PK Metrics ───────────────────────────────────────────────────────────
  checkPageBreak(40);
  addSectionTitle("Pharmacokinetic Metrics");
  addKeyValue("Cmax", sim.cmax_mg_l?.toFixed(4), "mg/L");
  addKeyValue("Cmin", sim.cmin_mg_l?.toFixed(4), "mg/L");
  addKeyValue("AUC",  sim.auc_mg_h_l?.toFixed(4), "mg·h/L");

  // Flags
  y += 2;
  const flagColor = sim.flag_too_high || sim.flag_too_low ? [200, 0, 0] : [0, 140, 0];
  pdf.setTextColor(...flagColor);
  addText(
    `⚠ Flags: ${sim.flag_too_high ? "Concentration TOO HIGH  " : ""}${sim.flag_too_low ? "Concentration TOO LOW" : ""}${!sim.flag_too_high && !sim.flag_too_low ? "None — within therapeutic range" : ""}`,
    10, true
  );
  pdf.setTextColor(0, 0, 0);

  // ── Therapeutic Window ───────────────────────────────────────────────────
  checkPageBreak(30);
  addSectionTitle("Therapeutic Window");
  const tw = sim.therapeutic_window ?? {};
  addKeyValue("Lower Bound", tw.lower_mg_l?.toFixed(4), "mg/L");
  addKeyValue("Upper Bound", tw.upper_mg_l?.toFixed(4), "mg/L");
  addKeyValue("Source", tw.source);

  // ── Therapeutic Evaluation ───────────────────────────────────────────────
  checkPageBreak(40);
  addSectionTitle("Therapeutic Evaluation");
  const te = sim.therapeutic_eval ?? {};
  Object.entries(te).forEach(([k, v]) => {
    addKeyValue(k, typeof v === "number" ? v.toFixed(3) : v);
    checkPageBreak(8);
  });

  // ── Patient Context ───────────────────────────────────────────────────────
  checkPageBreak(50);
  addSectionTitle("Patient Context");
  const pc = sim.patient_context ?? {};
  const patientFields = [
    ["Age",                  pc.age,                          ""],
    ["Sex",                  pc.sex,                          ""],
    ["Weight",               pc.weight_kg,                    "kg"],
    ["Height",               pc.height_cm,                    "cm"],
    ["Serum Creatinine",     pc.serum_creatinine_mg_dl,       "mg/dL"],
    ["Creatinine Clearance", pc.creatinine_clearance_ml_min,  "mL/min"],
    ["CKD Stage",            pc.ckd_stage,                    ""],
    ["Pregnant",             pc.is_pregnant,                  ""],
    ["Liver Disease",        pc.liver_disease_status,         ""],
    ["Albumin",              pc.albumin_g_dl,                 "g/dL"],
  ];
  patientFields.forEach(([label, val, unit]) => {
    checkPageBreak(8);
    addKeyValue(label, val, unit);
  });

  if (pc.conditions?.length) {
    checkPageBreak(10);
    addKeyValue("Conditions", pc.conditions.join(", "));
  }
  if (pc.current_medications?.length) {
    checkPageBreak(10);
    addKeyValue("Current Medications", pc.current_medications.join(", "));
  }

  // ── ADE Screening ─────────────────────────────────────────────────────────
  checkPageBreak(30);
  addSectionTitle("ADE Screening");
  const ade = sim.ade_screening ?? {};
  Object.entries(ade).forEach(([k, v]) => {
    checkPageBreak(8);
    const display = typeof v === "object" ? JSON.stringify(v) : v;
    addKeyValue(k, display);
  });

  // ── Concentration–Time Chart (screenshot) ─────────────────────────────────
  if (chartRef?.current) {
    checkPageBreak(90);
    addSectionTitle("Concentration–Time Profile");
    y += 2;
    try {
      const canvas = await html2canvas(chartRef.current, {
        scale: 2,
        backgroundColor: "#ffffff",
        useCORS: true,
      });
      const imgData = canvas.toDataURL("image/png");
      const imgH = (canvas.height / canvas.width) * contentW;
      checkPageBreak(imgH + 5);
      pdf.addImage(imgData, "PNG", margin, y, contentW, imgH);
      y += imgH + 5;
    } catch (err) {
      addText("(Chart could not be rendered)", 9);
      console.warn("Chart screenshot failed:", err);
    }
  }

  // ── Footer on every page ──────────────────────────────────────────────────
  const totalPages = pdf.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    pdf.setPage(i);
    pdf.setFontSize(8);
    pdf.setTextColor(150, 150, 150);
    pdf.text(
      `Page ${i} of ${totalPages}  |  Confidential – For clinical use only`,
      pageW / 2,
      pdf.internal.pageSize.getHeight() - 6,
      { align: "center" }
    );
  }

  pdf.save(`simulation_${sim.id ?? "report"}.pdf`);
} 
// Finalized the design/look of the pdf export