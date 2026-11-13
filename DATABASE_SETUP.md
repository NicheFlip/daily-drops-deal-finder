# PostgreSQL integration (optional)
The GitHub Pages frontend remains public and static. Database credentials must **never** be included in JavaScript, HTML or committed files.

1. Create a PostgreSQL database with SSL enabled (for example, a managed PostgreSQL service). Review the provider's free-tier limits and retention policy.
2. In GitHub repository Settings → Secrets and variables → Actions, create a repository secret named `DATABASE_URL` containing the provider's PostgreSQL connection string with SSL enforced (typically `?sslmode=require`).
3. Run **Amazon automated deal research** manually. The workflow runs offline regression tests, scans the official Amazon API, then writes the latest observations and historical discoveries into PostgreSQL. It also continues publishing the existing JSON website feed.
4. Check Actions logs for `PostgreSQL observation archive updated.` If the secret is missing, the workflow explicitly reports that PostgreSQL was skipped.

Tables: `products`, `price_observations`, `discoveries`. Primary keys prevent duplicate imports, indexes support historical queries, and no expiration/deletion job is installed. Database retention still depends on the hosting provider and backups.

This is an archive integration, **not** a public database API. GitHub Pages cannot safely connect directly to PostgreSQL. A read-only server/API and pagination will be needed to browse large database histories from the website. Walmart individual products cannot be imported until a licensed/authorized Walmart product-data source exists. Never insert unverified Walmart search results as product observations.
