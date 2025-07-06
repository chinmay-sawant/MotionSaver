// Theme switcher logic
const themeToggle = document.getElementById("theme-toggle");
const body = document.body;

function applyTheme(theme) {
  body.setAttribute("data-theme", theme);
  themeToggle.textContent = theme === "dark" ? "🌙" : "☀️";
  localStorage.setItem("theme", theme);
}

themeToggle.addEventListener("click", () => {
  const newTheme =
    body.getAttribute("data-theme") === "dark" ? "light" : "dark";
  applyTheme(newTheme);
});

// Apply saved theme on load
const savedTheme = localStorage.getItem("theme") || "dark"; // Default to dark
applyTheme(savedTheme);

// Fetch and display GitHub releases
document.addEventListener("DOMContentLoaded", () => {
  const releasesContainer = document.getElementById("releases-container");
  const repo = "chinmay-sawant/MotionSaver";

  // Improved markdown to HTML converter for GitHub releases
  function markdownToHtml(md) {
    if (!md) return "";
    let html = md.trim();

    // Remove excessive whitespace (more than 2 consecutive newlines)
    html = html.replace(/(\r?\n){3,}/g, "\n\n");

    // Horizontal rule --- or ***
    html = html.replace(/^\s*([-*_]){3,}\s*$/gm, "<hr>");

    // Code blocks (```...```)
    html = html.replace(/```([\s\S]*?)```/g, function (_, code) {
      return `<pre><code>${code
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")}</code></pre>`;
    });

    // Inline code (`...`)
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Images ![alt](url)
    html = html.replace(
      /!\[([^\]]*)\]\(([^)]+)\)/g,
      '<img alt="$1" src="$2" />'
    );

    // Links [text](url)
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank">$1</a>'
    );

    // Headings ####, ###, ##, #
    html = html.replace(/^#### (.*)$/gim, "<h4>$1</h4>");
    html = html.replace(/^### (.*)$/gim, "<h3>$1</h3>");
    html = html.replace(/^## (.*)$/gim, "<h2>$1</h2>");
    html = html.replace(/^# (.*)$/gim, "<h1>$1</h1>");

    // Blockquotes
    html = html.replace(/^> (.*)$/gim, "<blockquote>$1</blockquote>");

    // Bold **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    // Italic *text*
    html = html.replace(/(\s|^)\*([^*]+)\*(\s|$)/g, "$1<em>$2</em>$3");

    // Unordered lists
    html = html.replace(/^\s*[-*+] (.*)$/gim, "<li>$1</li>");
    // Ordered lists
    html = html.replace(/^\s*\d+\. (.*)$/gim, "<li>$1</li>");

    // Wrap consecutive <li> in <ul>
    html = html.replace(/((?:<li>[\s\S]*?<\/li>\s*)+)/g, function (match) {
      // Only wrap if not already inside <ul>
      if (!/^<ul>/.test(match)) {
        return `<ul>${match.replace(/\s*$/,'')}</ul>`;
      }
      return match;
    });

    // Remove duplicate <ul> tags
    html = html.replace(/<\/ul>\s*<ul>/g, "");

    // Paragraphs: add <br> for single line breaks, <p> for double
    html = html.replace(/\n{2,}/g, "</p><p>");
    html = html.replace(/\n/g, "<br>");

    // Wrap in <p> if not already block element
    html = "<p>" + html + "</p>";
    html = html.replace(
      /<p>(\s*<(h\d|ul|pre|blockquote|img|hr)[^>]*>)/g,
      "$1"
    );
    html = html.replace(
      /(<\/h\d>|<\/ul>|<\/pre>|<\/blockquote>|<\/img>|<hr>)\s*<\/p>/g,
      "$1"
    );

    // Remove empty <p></p>
    html = html.replace(/<p>\s*<\/p>/g, "");

    return html;
  }

  fetch(`https://api.github.com/repos/${repo}/releases`)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((releases) => {
      releasesContainer.innerHTML = ""; // Clear loading message
      if (releases.length === 0) {
        releasesContainer.innerHTML = "<p>No releases found.</p>";
        return;
      }
      releases.forEach((release) => {
        const releaseElement = document.createElement("details");

        // Use improved markdown parser
        let bodyHtml = markdownToHtml(release.body || "");

        releaseElement.innerHTML = `
                      <summary>
                          ${release.name}
                          <span class="release-tag">${
                            release.tag_name
                          }</span>
                          <small> - Published on ${new Date(
                            release.published_at
                          ).toLocaleDateString()}</small>
                      </summary>
                      <div class="details-content">
                          ${
                            bodyHtml ||
                            "<p>No description provided for this release.</p>"
                          }
                          <p><strong>Assets:</strong></p>
                          <ul>
                              ${release.assets
                                .map(
                                  (asset) => `
                                  <li><a href="${
                                    asset.browser_download_url
                                  }" target="_blank">${
                                    asset.name
                                  }</a> (${(
                                    asset.size /
                                    1024 /
                                    1024
                                  ).toFixed(2)} MB)</li>
                              `
                                )
                                .join("")}
                          </ul>
                      </div>
                  `;
        releasesContainer.appendChild(releaseElement);
      });
    })
    .catch((error) => {
      console.error("Error fetching releases:", error);
      releasesContainer.innerHTML =
        "<p>Could not load releases. Please check the console for errors or try again later.</p>";
    });
});
