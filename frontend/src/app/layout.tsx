import { Outlet, Link } from "react-router-dom";

export default function Layout() {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <header style={{ marginBottom: "1rem" }}>
        <Link to="/" style={{ textDecoration: "none", color: "black" }}>
          <h1>Digital Twin</h1>
        </Link>
      </header>
      <Outlet />
    </div>
  );
}
