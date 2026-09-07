import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { getCustomers } from "../services/customerService";
import { getPlaces } from "../services/placeService";
import PageHeader from "../components/PageHeader";
import { FiPrinter, FiRefreshCw, FiCalendar, FiUsers, FiMapPin } from "react-icons/fi";
import logoWatermark from "../assets/Vel finance logo white.png";

// ─── Date Utilities ────────────────────────────────────────────────────────

function toInputDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function toDisplayDate(isoStr) {
  if (!isoStr) return "";
  const [y, m, d] = isoStr.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

// ─── DL Daily Collection Amount ─────────────────────────────────────────────
// Source of truth: AddCustomer.jsx calculateLoanDetails()
//   dailyCollection = loan_amount / 100  (DL only)
// Furniture customers: blank cell — collector writes manually.

function getDailyAmount(customer) {
  if (customer.type !== "DL") return "";
  const loanAmount = Number(customer.loan_amount) || 0;
  if (loanAmount <= 0) return "";
  return String(Math.round(loanAmount / 100));
}

// ─── A4 Landscape Layout Constants ──────────────────────────────────────────
//
// Physical paper:  297 mm wide × 210 mm tall  (A4 landscape)
// @page margin:    10 mm all sides
//   Printable width:  297 - 20 = 277 mm
//   Printable height: 210 - 20 = 190 mm
//
// Vertical budget (190 mm):
//   Header block (title + subtitle + date)    =   9.5 mm
//   Table thead row                           =   4.5 mm
//   Table outer borders (top + bottom)        =   0.5 mm
//   Safety buffer                             =  12.5 mm  (guarantees iOS Safari never overflows)
//   Available for data rows                   = 163.0 mm
//
// Row height: 6.0 mm + 0.26 mm border = 6.26 mm pitch
// Rows per half = floor(163.0 / 6.26) = 26
// Items per page = 26 × 2 = 52
//
// Place header row: 4.5 mm height (shorter than customer row, giving even more safety)

const AVAIL_ROW_MM   = 163.0;
const ROW_PITCH_MM   = 6.26;
const ROWS_PER_HALF  = Math.floor(AVAIL_ROW_MM / ROW_PITCH_MM); // 26
const ITEMS_PER_PAGE = ROWS_PER_HALF * 2;                       // 52

// ─── Row-stream builder ──────────────────────────────────────────────────────
//
// Produces a flat array of "row items" that the pagination engine splits into
// left and right half-tables. Each item is one of:
//
//   { type: "place-header", label: "TARKAS — 42 CUSTOMERS" }
//   { type: "customer", customer: { ... } }
//
// This lets place headers flow naturally with customers without wasting paper.

function buildRowStream(places, activeCustomers) {
  // Group customers by place_id
  const byPlace = {};
  activeCustomers.forEach((c) => {
    const key = c.place_id != null ? c.place_id : "__unassigned__";
    if (!byPlace[key]) byPlace[key] = [];
    byPlace[key].push(c);
  });

  const stream = [];

  // 1. Assigned places in priority order
  places.forEach((place) => {
    const customers = byPlace[place.id] || [];
    if (customers.length === 0) return; // skip empty places on the sheet
    // Sort customers within place by customer_id ASC
    const sorted = [...customers].sort((a, b) => a.customer_id - b.customer_id);
    stream.push({
      type: "place-header",
      label: `${place.name.toUpperCase()} — ${sorted.length} CUSTOMER${sorted.length !== 1 ? "S" : ""}`,
    });
    sorted.forEach((c) => stream.push({ type: "customer", customer: c }));
  });

  // 2. Unassigned customers last
  const unassigned = (byPlace["__unassigned__"] || []).sort(
    (a, b) => a.customer_id - b.customer_id
  );
  if (unassigned.length > 0) {
    stream.push({
      type: "place-header",
      label: `UNASSIGNED — ${unassigned.length} CUSTOMER${unassigned.length !== 1 ? "S" : ""}`,
    });
    unassigned.forEach((c) => stream.push({ type: "customer", customer: c }));
  }

  return stream;
}

// ─── Pagination engine ───────────────────────────────────────────────────────
//
// Splits the row stream into A4 pages, each with a left and right half-table.
// Each half holds up to ROWS_PER_HALF row items (place-headers and customer rows).
// Proven chunk-and-slice pattern matching the working pre-regression implementation.

function paginateStream(stream) {
  const pages = [];
  for (let i = 0; i < stream.length; i += ITEMS_PER_PAGE) {
    const chunk = stream.slice(i, i + ITEMS_PER_PAGE);
    const mid   = Math.min(chunk.length, ROWS_PER_HALF);
    pages.push({
      left:  chunk.slice(0, mid),
      right: chunk.slice(mid),
    });
  }
  return pages;
}

// ─── Render a single half-table row ─────────────────────────────────────────

function PrintRow({ item }) {
  if (item.type === "place-header") {
    return (
      <tr className="print-place-header-row">
        <td colSpan={5} className="print-place-header-cell">
          {item.label}
        </td>
      </tr>
    );
  }
  const c = item.customer;
  return (
    <tr className="print-row">
      <td className="col-id">{c.customer_id}</td>
      <td className="col-name">{c.name}</td>
      <td className="col-amount">{getDailyAmount(c)}</td>
      <td className="col-extra"></td>
      <td className="col-balance"></td>
    </tr>
  );
}

// ─── CollectionSheet component ───────────────────────────────────────────────

function CollectionSheet() {
  const today = toInputDate(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const [customers, setCustomers]       = useState([]);
  const [places, setPlaces]             = useState([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [allCustomers, allPlaces] = await Promise.all([
        getCustomers(),
        getPlaces(),
      ]);

      // Active filter: loan_given === true
      const active = allCustomers.filter((c) => c.loan_given);

      console.log("[CollectionSheet] Data loaded", {
        totalFromAPI:  allCustomers.length,
        totalActive:   active.length,
        totalPlaces:   allPlaces.length,
        rowsPerHalf:   ROWS_PER_HALF,
      });

      setCustomers(active);
      setPlaces(allPlaces);
    } catch (err) {
      console.error("[CollectionSheet] Error:", err);
      setError("Unable to load collection sheet data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  // Build the row stream and paginate
  const rowStream = buildRowStream(places, customers);
  const pages     = paginateStream(rowStream);

  const displayDate = toDisplayDate(selectedDate);

  function handlePrint() {
    const originalTitle = document.title;
    const dateFormatted = toDisplayDate(selectedDate);
    document.title = dateFormatted
      ? `VEL Finance - Daily Collection - ${dateFormatted}`
      : "VEL Finance - Daily Collection";

    const restoreTitle = () => {
      document.title = originalTitle;
      window.removeEventListener("afterprint", restoreTitle);
    };

    window.addEventListener("afterprint", restoreTitle);
    try {
      window.print();
    } finally {
      setTimeout(restoreTitle, 500);
    }
  }

  // Screen-side summary
  const assignedCount   = customers.filter((c) => c.place_id != null).length;
  const unassignedCount = customers.length - assignedCount;

  return (
    <>
      {/* SCREEN UI */}
      <div className="no-print max-w-2xl mx-auto px-5 py-6 pb-10">
        <PageHeader
          title="Collection Sheet"
          subtitle="Generate a printable daily collection worksheet grouped by collection route."
        />

        <div className="bg-[#182238] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">

          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
              <FiCalendar size={15} />
              Collection Date
            </label>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="w-full bg-[#0f172a] border border-slate-700/80 rounded-xl px-4 py-3.5 text-white color-scheme-dark focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            />
          </div>

          {!loading && !error && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <FiUsers size={15} />
                <span>
                  <span className="text-emerald-400 font-semibold">{customers.length}</span>{" "}
                  active customers &middot;{" "}
                  <span className="text-emerald-400 font-semibold">{pages.length}</span>{" "}
                  page{pages.length !== 1 ? "s" : ""}
                </span>
              </div>
              {places.length > 0 && (
                <div className="flex items-center gap-2 text-sm text-slate-400">
                  <FiMapPin size={15} />
                  <span>
                    <span className="text-sky-400 font-semibold">{places.length}</span> place{places.length !== 1 ? "s" : ""}
                    {unassignedCount > 0 && (
                      <span className="text-amber-400"> &middot; {unassignedCount} unassigned</span>
                    )}
                  </span>
                </div>
              )}
            </div>
          )}

          {loading && (
            <div className="flex items-center gap-3 text-slate-400 text-sm py-2">
              <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              Loading collection data…
            </div>
          )}

          {error && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-start justify-between gap-4">
              <p className="text-rose-400 text-sm">{error}</p>
              <button onClick={loadData} className="flex items-center gap-1.5 text-xs text-rose-400 hover:text-rose-300 font-semibold shrink-0 transition">
                <FiRefreshCw size={13} /> Retry
              </button>
            </div>
          )}

          {!loading && !error && customers.length === 0 && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
              <p className="text-amber-400 text-sm">No active customers available for this collection sheet.</p>
            </div>
          )}

          <button
            onClick={handlePrint}
            disabled={loading || !!error || customers.length === 0}
            className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed active:scale-[0.98] rounded-xl py-3.5 font-semibold text-white shadow-lg shadow-emerald-950/40 transition-all"
          >
            <FiPrinter size={18} />
            Print Collection Sheet
          </button>
        </div>
      </div>

      {/* PRINT DOCUMENT — React Portal renders directly on <body>, outside #root */}
      {createPortal(
        <div className="print-document">
          {pages.map((page, pageIdx) => (
            <div key={pageIdx} className="print-page">

              {/* Centered background watermark */}
              <div className="print-watermark" aria-hidden="true">
                <img src={logoWatermark} alt="" className="print-watermark-img" />
              </div>

              <div className="print-header">
                <div className="print-title">VEL FINANCE</div>
                <div className="print-subtitle">Daily Collection Sheet</div>
                <div className="print-date">Date: {displayDate}</div>
              </div>

              <div className="print-tables-row">
                {/* LEFT TABLE */}
                <div className="print-table-wrap">
                  <table className="print-table">
                    <thead>
                      <tr>
                        <th className="col-id">ID</th>
                        <th className="col-name">Name</th>
                        <th className="col-amount">Amount</th>
                        <th className="col-extra">Extra</th>
                        <th className="col-balance">Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {page.left.map((item, i) => (
                        <PrintRow key={i} item={item} />
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="print-center-gap" aria-hidden="true" />

                {/* RIGHT TABLE */}
                <div className="print-table-wrap">
                  {page.right.length > 0 && (
                    <table className="print-table">
                      <thead>
                        <tr>
                          <th className="col-id">ID</th>
                          <th className="col-name">Name</th>
                          <th className="col-amount">Amount</th>
                          <th className="col-extra">Extra</th>
                          <th className="col-balance">Balance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {page.right.map((item, i) => (
                          <PrintRow key={i} item={item} />
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>

            </div>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}

export default CollectionSheet;
