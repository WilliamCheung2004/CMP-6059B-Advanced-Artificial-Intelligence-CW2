import { useState } from 'react'
import NavBar from "./components/NavBar"
import LandingPage from "./pages/LandingPage"
import ChatPage from "./pages/ChatPage"

function App() {
  const [page, setPage] = useState(() => {
    return localStorage.getItem('trainbot_page') || "landing"
  })

  const [helpText, setHelpText] = useState("")

  function goToChat() {
    setPage("chat")
    localStorage.setItem('trainbot_page', 'chat')
  }

  function handleHelpClick() {
    goToChat()
    setHelpText("I need help")
  }

  return (
    <>
      {page !== "landing" && <NavBar goChat={goToChat} onHelp={handleHelpClick} />}
      {page === "landing" && <LandingPage startChat={goToChat} />}
      {page === "chat" && <ChatPage helpText={helpText} setHelpText={setHelpText} />}
    </>
  )
}

export default App;