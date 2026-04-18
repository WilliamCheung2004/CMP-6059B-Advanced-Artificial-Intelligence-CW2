import { useState } from 'react'
import NavBar from "./components/NavBar"
import LandingPage from "./pages/LandingPage"
import ChatPage from "./pages/ChatPage"

function App() {
  const [page, setPage] = useState("landing")

  return (
    <>
      {page !== "landing" && <NavBar goChat={() => setPage("chat")} />}
      {page === "landing" && <LandingPage startChat={() => setPage("chat")} />}
      {page === "chat" && <ChatPage />}
    </>
  )
}

export default App;