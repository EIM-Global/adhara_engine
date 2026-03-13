const http = require("http");

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  if (req.url === "/api/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "healthy", uptime: process.uptime() }));
    return;
  }

  res.writeHead(200, { "Content-Type": "text/html" });
  res.end(`
    <!DOCTYPE html>
    <html>
    <head><title>Adhara Engine Test App</title></head>
    <body>
      <h1>Adhara Engine Test App</h1>
      <p><strong>ADHARA_API_URL:</strong> ${process.env.ADHARA_API_URL || "not set"}</p>
      <p><strong>ADHARA_WORKSPACE_ID:</strong> ${process.env.ADHARA_WORKSPACE_ID || "not set"}</p>
      <p><strong>ADHARA_PUBLIC_URL:</strong> ${process.env.ADHARA_PUBLIC_URL || "not set"}</p>
      <p><strong>NODE_ENV:</strong> ${process.env.NODE_ENV || "not set"}</p>
      <p><em>Uptime: ${Math.round(process.uptime())}s</em></p>
    </body>
    </html>
  `);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Test app listening on port ${PORT}`);
});
