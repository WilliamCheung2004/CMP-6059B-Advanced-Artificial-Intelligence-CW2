import "../styles/navbar.css"

export default function Navbar({ goChat }) {
    return (
        <div className="navbar">
            <div className="navLeft">
                <span className="logoText">TrainBot</span>
            </div>

            <div className="navRight">
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