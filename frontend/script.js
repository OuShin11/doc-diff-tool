console.log("SCRIPT LOADED");

window.addEventListener("beforeunload", () => {
  console.log("PAGE IS RELOADING");
});

window.addEventListener("DOMContentLoaded", () => {
  const compareBtn = document.getElementById("compareBtn");
  const statusEl = document.getElementById("status");
  const summaryEl = document.getElementById("summary");
  const diffCountEl = document.getElementById("diffCount");
  const csvLinkEl = document.getElementById("csvLink");
  const imagesSectionEl = document.getElementById("imagesSection");
  const beforeImagesEl = document.getElementById("beforeImages");
  const afterImagesEl = document.getElementById("afterImages");

  const API_BASE = "http://127.0.0.1:8000";
  let isRunning = false;

  compareBtn.addEventListener("click", handleCompare);

  async function handleCompare(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    if (isRunning) {
      console.log("IGNORED: already running");
      // return false;
    }

    isRunning = true;
    console.log("CLICKED");

    const oldFile = document.getElementById("oldFile").files[0];
    const newFile = document.getElementById("newFile").files[0];

    if (!oldFile || !newFile) {
      statusEl.textContent = "Please select both PDF files.";
      isRunning = false;
      // return false;
    }

    statusEl.textContent = "Processing...";
    summaryEl.classList.add("hidden");
    imagesSectionEl.classList.add("hidden");
    beforeImagesEl.innerHTML = "";
    afterImagesEl.innerHTML = "";
    diffCountEl.textContent = "";
    csvLinkEl.href = "#";
    csvLinkEl.style.display = "none";

    const formData = new FormData();
    formData.append("old_file", oldFile);
    formData.append("new_file", newFile);

    try {
      const response = await fetch(`${API_BASE}/compare/`, {
        method: "POST",
        body: formData,
      });

      const text = await response.text();
      console.log("RAW RESPONSE:", text);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${text}`);
      }

      let data;
      try {
        data = JSON.parse(text);
      } catch (parseError) {
        console.error("JSON parse failed:", parseError);
        throw new Error("Response is not valid JSON");
      }

      console.log("PARSED DATA:", data);

      diffCountEl.textContent = `Detected changes: ${data.diff_count ?? 0}`;

      if (data.csv_url) {
        csvLinkEl.href = `${API_BASE}${data.csv_url}`;
        csvLinkEl.style.display = "inline-block";
      } else {
        csvLinkEl.style.display = "none";
      }

      renderImages(beforeImagesEl, data.highlight_urls?.before || []);
      renderImages(afterImagesEl, data.highlight_urls?.after || []);

      summaryEl.classList.remove("hidden");
      imagesSectionEl.classList.remove("hidden");
      statusEl.textContent = "Completed.";
    } catch (error) {
      console.error("ERROR:", error);
      statusEl.textContent = `Error: ${error.message}`;
    } finally {
      isRunning = false;
    }

    // return false;
  }

  function renderImages(container, urls) {
    container.innerHTML = "";

    if (!urls || urls.length === 0) {
      container.innerHTML = "<p>No highlighted pages.</p>";
      return;
    }

    urls.forEach((url) => {
      const card = document.createElement("div");
      card.className = "image-card";

      const link = document.createElement("a");
      link.href = `${API_BASE}${url}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      const img = document.createElement("img");
      img.src = `${API_BASE}${url}`;
      img.alt = "Highlighted page";

      link.appendChild(img);
      card.appendChild(link);
      container.appendChild(card);
    });
  }
});