import { useState } from 'react'
import NavBar from "./components/NavBar"
import LandingPage from "./pages/LandingPage"
import ChatPage from "./pages/ChatPage"

function App() {
  const [page, setPage] = useState(() => {
    return localStorage.getItem('trainbot_page') || "landing"
  })

  function goToChat() {
    setPage("chat")
    localStorage.setItem('trainbot_page', 'chat')
  }

  return (
    <>
      {page !== "landing" && <NavBar goChat={goToChat} />}
      {page === "landing" && <LandingPage startChat={goToChat} />}
      {page === "chat" && <ChatPage />}
    </>
  )
}

export default App;