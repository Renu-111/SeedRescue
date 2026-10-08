(() => {
  "use strict";

  /*
   * ============================================================
   * SEEDRESCUE+
   * NON-INVASIVE INTELLIGENCE OVERLAY
   * ============================================================
   *
   * IMPORTANT:
   * This file does NOT modify:
   *
   * - app.py
   * - engine.py
   * - datasets
   * - ML model
   * - database
   * - OSM data
   * - WorldPop data
   *
   * It only reads information already visible on the dashboard.
   *
   * FEATURES:
   * 1. TATTVA Decision Lens
   * 2. Resilience Score
   * 3. Weakest-Link Analysis
   * 4. Response Action Queue
   * 5. Observed State
   * 6. Operator Decision Notes
   */

  const APP = "srx";

  let root = null;
  let open = false;
  let observer = null;
  let lastSnapshot = "";

  // ------------------------------------------------------------
  // BASIC HELPERS
  // ------------------------------------------------------------

  const clamp = (n, min, max) => {
    return Math.max(min, Math.min(max, n));
  };

  const num = (value) => {
    if (value == null) return null;

    const match = String(value)
      .replace(/,/g, "")
      .match(/-?\d+(?:\.\d+)?/);

    return match ? Number(match[0]) : null;
  };

  function bodyText() {
    if (!document.body) return "";

    return document.body.innerText.replace(/\s+/g, " ");
  }

  // ------------------------------------------------------------
  // READ DASHBOARD VALUES
  // ------------------------------------------------------------

  function extract(label, aliases = []) {

    const text = bodyText();

    const terms = [label, ...aliases];

    for (const term of terms) {

      const escaped = term.replace(
        /[.*+?^${}()|[\]\\]/g,
        "\\$&"
      );

      const regex = new RegExp(
        escaped +
        "\\s*[:=]?\\s*" +
        "(-?\\d+(?:\\.\\d+)?)",
        "i"
      );

      const match = text.match(regex);

      if (match) {
        return num(match[1]);
      }
    }

    return null;
  }

  function extractMetric(label, aliases = []) {

    const value = extract(label, aliases);

    return value == null ? 0 : value;
  }

  // ------------------------------------------------------------
  // GET CURRENT SEEDRESCUE STATE
  // ------------------------------------------------------------

  function getSnapshot() {

    const text = bodyText();

    const risk =
      extractMetric("Risk Score");

    const recovery =
      extractMetric("Recovery Score");

    const displaced =
      extractMetric("Displaced");

    const medical =
      extractMetric("Medical Demand");

    const safeRoads =
      extractMetric("Safe Roads");

    const sheltered =
      extractMetric("Sheltered");

    const aiRisk =
      extractMetric(
        "AI ML Risk",
        [
          "AI ML Risk",
          "AI MLRisk"
        ]
      );

    const aiDisplaced =
      extractMetric("AI Displaced");

    /*
     * Count visible operational indicators.
     */

    const blocked =
      (text.match(/\bblocked\b/gi) || []).length;

    const deficits =
      (text.match(/\bDeficit\b/gi) || []).length;

    const critical =
      (text.match(/\bCRITICAL\b/gi) || []).length;

    const high =
      (text.match(/\bHIGH\b/gi) || []).length;

    /*
     * Detect current disaster type.
     */

    const hazardMatch =
      text.match(
        /Disaster Type\s+([A-Za-z]+)/i
      );

    const hazard =
      hazardMatch
        ? hazardMatch[1]
        : "Current scenario";

    return {
      hazard,
      risk,
      recovery,
      displaced,
      medical,
      safeRoads,
      sheltered,
      aiRisk,
      aiDisplaced,
      blocked,
      deficits,
      critical,
      high
    };
  }

  // ------------------------------------------------------------
  // DERIVE DECISION-SUPPORT INDICATORS
  // ------------------------------------------------------------

  function derive(state) {

    /*
     * IMPORTANT:
     *
     * These are NOT new ML predictions.
     *
     * They are dashboard-level decision-support heuristics.
     */

    const riskPressure =
      clamp(
        (state.risk || state.aiRisk || 0) / 100,
        0,
        1
      );

    const recoveryPressure =
      1 -
      clamp(
        (state.recovery || 0) / 100,
        0,
        1
      );

    // ----------------------------------------------------------
    // MOBILITY PRESSURE
    // ----------------------------------------------------------

    let roadPressure = 0;

    if (state.safeRoads > 0) {

      roadPressure =
        clamp(
          (
            state.blocked /
            (
              state.safeRoads +
              state.blocked
            )
          ) * 1.5,
          0,
          1
        );

    } else {

      roadPressure =
        state.blocked
          ? 0.8
          : 0;
    }

    // ----------------------------------------------------------
    // RESOURCE PRESSURE
    // ----------------------------------------------------------

    const resourcePressure =
      clamp(
        (
          state.deficits * 0.18
        ) +
        (
          state.critical * 0.22
        ) +
        (
          state.high * 0.08
        ),
        0,
        1
      );

    // ----------------------------------------------------------
    // MEDICAL PRESSURE
    // ----------------------------------------------------------

    const medicalPressure =
      state.medical > 0
        ? clamp(
            state.medical / 500,
            0,
            1
          )
        : 0;

    // ----------------------------------------------------------
    // RESILIENCE SCORE
    // ----------------------------------------------------------

    const resilience =
      Math.round(
        clamp(
          100 -
          (
            riskPressure * 30 +
            recoveryPressure * 25 +
            roadPressure * 20 +
            resourcePressure * 15 +
            medicalPressure * 10
          ),
          0,
          100
        )
      );

    // ----------------------------------------------------------
    // SYSTEM COMPONENTS
    // ----------------------------------------------------------

    const links = [

      {
        name: "Risk containment",
        score:
          Math.round(
            100 -
            riskPressure * 100
          ),
        icon: "⚠️"
      },

      {
        name: "Recovery readiness",
        score:
          Math.round(
            state.recovery || 0
          ),
        icon: "🛠️"
      },

      {
        name: "Mobility resilience",
        score:
          Math.round(
            100 -
            roadPressure * 100
          ),
        icon: "🛣️"
      },

      {
        name: "Resource resilience",
        score:
          Math.round(
            100 -
            resourcePressure * 100
          ),
        icon: "📦"
      },

      {
        name: "Medical readiness",
        score:
          Math.round(
            100 -
            medicalPressure * 100
          ),
        icon: "🏥"
      }

    ];

    /*
     * Lowest score = weakest operational link.
     */

    links.sort(
      (a, b) =>
        a.score - b.score
    );

    // ----------------------------------------------------------
    // ACTION QUEUE
    // ----------------------------------------------------------

    const actions = [

      {
        title:
          "Protect the weakest link",

        detail:
          `${links[0].name} is the current limiting factor.`,

        priority:
          links[0].score < 40
            ? "CRITICAL"
            : links[0].score < 65
              ? "HIGH"
              : "WATCH"
      },

      {
        title:
          "Verify the operational bottleneck",

        detail:
          "Confirm that the highest-impact road, resource or medical constraint is actionable.",

        priority:
          roadPressure > 0.45
            ? "HIGH"
            : "WATCH"
      },

      {
        title:
          "Review downstream consequences",

        detail:
          "Check whether displaced population, medical demand and accessibility changed together.",

        priority:
          (
            state.displaced > 0 ||
            state.medical > 0
          )
            ? "MEDIUM"
            : "WATCH"
      }

    ];

    return {
      resilience,
      links,
      actions
    };
  }

  // ------------------------------------------------------------
  // HTML ESCAPE
  // ------------------------------------------------------------

  function esc(value) {

    return String(value ?? "")
      .replace(
        /[&<>"']/g,
        character => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;"
        }[character])
      );
  }

  // ------------------------------------------------------------
  // RENDER PANEL
  // ------------------------------------------------------------

  function render() {

    if (!root) return;

    const state =
      getSnapshot();

    const decision =
      derive(state);

    const weakest =
      decision.links[0];

    root.innerHTML = `

      <div class="${APP}-bar">

        <div class="${APP}-brand">
          ✦ SeedRescue+
        </div>

        <div class="${APP}-sub">
          TATTVA Decision Lens
        </div>

        <button
          id="${APP}-close"
          class="${APP}-close"
        >
          ×
        </button>

      </div>


      <div class="${APP}-content">


        <!-- =================================================
             HERO
        ================================================== -->

        <section class="${APP}-hero">

          <div>

            <div class="${APP}-eyebrow">
              CURRENT OPERATIONAL STATE
            </div>

            <h2>
              ${esc(state.hazard)}
              → adaptive response
            </h2>

            <p>
              Non-invasive intelligence layer.
              Existing SeedRescue calculations remain unchanged.
            </p>

          </div>


          <div class="${APP}-score">

            <span>
              RESILIENCE
            </span>

            <strong>
              ${decision.resilience}
            </strong>

            <small>
              / 100
            </small>

          </div>

        </section>


        <!-- =================================================
             TATTVA
        ================================================== -->

        <section class="${APP}-card">

          <div class="${APP}-title">
            TATTVA 2 · DRISHTAANTA
          </div>


          <div class="${APP}-flow">

            <div class="${APP}-node seed">

              <b>
                SEED
              </b>

              <span>
                Current disaster state
              </span>

            </div>


            <div class="${APP}-arrow">
              →
            </div>


            <div class="${APP}-node unfold">

              <b>
                UNFOLDING
              </b>

              <span>
                Risk · exposure · access · demand
              </span>

            </div>


            <div class="${APP}-arrow">
              →
            </div>


            <div class="${APP}-node manifest">

              <b>
                MANIFESTATION
              </b>

              <span>
                Recovery decisions
              </span>

            </div>

          </div>


          <div class="${APP}-quote">

            “Change the seed.
            Observe the consequence.
            Change the response.”

          </div>

        </section>


        <!-- =================================================
             WEAKEST LINK
        ================================================== -->

        <section class="${APP}-card">

          <div class="${APP}-title">
            WEAKEST-LINK ANALYSIS
          </div>


          <div class="${APP}-weak">

            <span class="${APP}-weak-icon">
              ${weakest.icon}
            </span>


            <div>

              <b>
                ${esc(weakest.name)}
              </b>

              <p>
                This is the current limiting factor
                in the operational picture.
              </p>

            </div>


            <strong>
              ${weakest.score}/100
            </strong>

          </div>


          <div class="${APP}-bars">

            ${decision.links.map(link => `

              <div class="${APP}-barrow">

                <span>
                  ${link.icon}
                  ${esc(link.name)}
                </span>


                <div>

                  <i
                    style="
                      width:${clamp(
                        link.score,
                        0,
                        100
                      )}%;
                    "
                  ></i>

                </div>


                <b>
                  ${link.score}
                </b>

              </div>

            `).join("")}

          </div>

        </section>


        <!-- =================================================
             ACTION QUEUE
        ================================================== -->

        <section class="${APP}-card">

          <div class="${APP}-title">
            RESPONSE ACTION QUEUE
          </div>


          ${decision.actions.map(
            (action, index) => `

            <div class="${APP}-action">

              <span class="${APP}-rank">
                ${index + 1}
              </span>


              <div>

                <b>
                  ${esc(action.title)}
                </b>

                <p>
                  ${esc(action.detail)}
                </p>

              </div>


              <em
                class="${action.priority.toLowerCase()}"
              >
                ${action.priority}
              </em>

            </div>

          `
          ).join("")}

        </section>


        <!-- =================================================
             OBSERVED STATE
        ================================================== -->

        <section class="${APP}-card">

          <div class="${APP}-title">
            OBSERVED STATE
          </div>


          <div class="${APP}-metrics">

            <span>
              Risk
              <b>
                ${state.risk || "—"}
              </b>
            </span>


            <span>
              Recovery
              <b>
                ${state.recovery || "—"}
              </b>
            </span>


            <span>
              Displaced
              <b>
                ${state.displaced || "—"}
              </b>
            </span>


            <span>
              Medical
              <b>
                ${state.medical || "—"}
              </b>
            </span>


            <span>
              Safe roads
              <b>
                ${state.safeRoads || "—"}
              </b>
            </span>


            <span>
              Sheltered
              <b>
                ${state.sheltered || "—"}
              </b>
            </span>

          </div>


          <p class="${APP}-note">

            This panel reads values already visible
            on the dashboard. It does not write to
            the dataset or replace the recovery engine.

          </p>

        </section>


        <!-- =================================================
             OPERATOR NOTE
        ================================================== -->

        <section class="${APP}-card">

          <div class="${APP}-title">
            OPERATOR DECISION NOTE
          </div>


          <textarea
            id="${APP}-note-input"
            placeholder="Record a human decision, assumption, or follow-up action..."
          ></textarea>


          <button
            id="${APP}-save-note"
            class="${APP}-primary"
          >
            Save local note
          </button>


          <div
            id="${APP}-saved"
            class="${APP}-saved"
          ></div>

        </section>


      </div>
    `;


    // --------------------------------------------------------
    // CLOSE BUTTON
    // --------------------------------------------------------

    root
      .querySelector(`#${APP}-close`)
      .onclick = () => toggle(false);


    // --------------------------------------------------------
    // LOCAL OPERATOR NOTE
    // --------------------------------------------------------

    const note =
      root.querySelector(
        `#${APP}-note-input`
      );

    const saved =
      root.querySelector(
        `#${APP}-saved`
      );


    note.value =
      localStorage.getItem(
        "seedrescue_operator_note"
      ) || "";


    root
      .querySelector(
        `#${APP}-save-note`
      )
      .onclick = () => {

        localStorage.setItem(
          "seedrescue_operator_note",
          note.value
        );

        saved.textContent =
          "✓ Saved locally in this browser.";
      };
  }

  // ------------------------------------------------------------
  // OPEN / CLOSE
  // ------------------------------------------------------------

  function toggle(value) {

    open = value;

    if (!root) return;

    root.classList.toggle(
      `${APP}-open`,
      open
    );

    if (open) {
      render();
    }
  }

  // ------------------------------------------------------------
  // MOUNT
  // ------------------------------------------------------------

  function mount() {

    if (
      document.getElementById(
        `${APP}-root`
      )
    ) {
      return;
    }


    // ----------------------------------------------------------
    // PANEL
    // ----------------------------------------------------------

    root =
      document.createElement(
        "aside"
      );

    root.id =
      `${APP}-root`;

    root.className =
      APP;

    document.body.appendChild(
      root
    );


    // ----------------------------------------------------------
    // LAUNCHER BUTTON
    // ----------------------------------------------------------

    const launcher =
      document.createElement(
        "button"
      );

    launcher.id =
      `${APP}-launcher`;

    launcher.className =
      `${APP}-launcher`;

    launcher.textContent =
      "✦ SR+";

    launcher.title =
      "Open SeedRescue Unique Features";

    launcher.onclick =
      () => toggle(!open);

    document.body.appendChild(
      launcher
    );


    render();


    // ----------------------------------------------------------
    // WATCH EXISTING DASHBOARD
    // ----------------------------------------------------------

    observer =
      new MutationObserver(() => {

        if (!open) return;

        const snapshot =
          JSON.stringify(
            getSnapshot()
          );

        if (
          snapshot !== lastSnapshot
        ) {

          lastSnapshot =
            snapshot;

          render();
        }

      });


    observer.observe(
      document.body,
      {
        childList: true,
        subtree: true,
        characterData: true
      }
    );
  }

  // ------------------------------------------------------------
  // START
  // ------------------------------------------------------------

  if (
    document.readyState === "loading"
  ) {

    document.addEventListener(
      "DOMContentLoaded",
      mount
    );

  } else {

    mount();

  }

})();