import "../styles/navbar.css"

export default function Navbar({ goChat }) {
    return (
        <div className="navbar">
            <div className="navLeft">
                <span className="logoText">TrainBot</span>
            </div>

            <div className="navRight">
                <button className="zoomBtn" onClick={() => document.body.style.zoom = "1.2"}>
                    Zoom In
                </button>
                <button className="zoomBtn" onClick={() => document.body.style.zoom = "1.0"}>
                    Zoom Out
                </button>
                <button className="chatBtn" onClick={goChat}>
                    Chat
                </button>
                <button className="helpBtn">
                    Help
                </button>
            </div>
        </div>
    )
}