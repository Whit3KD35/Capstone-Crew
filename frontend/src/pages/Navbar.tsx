import { useNavigate } from "react-router-dom";

export default function Navbar() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("token");
    alert("Successfully logged out");
    navigate("/");
  };

  const handleHome = () => {
    navigate("/choose");
  };

  return (
    <div style={{
      display: "flex",
      justifyContent: "flex-end",
      gap: "10px",
      padding: "10px"
    }}>
      <button onClick={handleHome}>Home</button>
      <button onClick={handleLogout}>Logout</button>
    </div>
  );
}