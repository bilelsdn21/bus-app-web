import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error("UI crash:", error, info);
  }
  reset = () => this.setState({ error: null });
  render() {
    if (this.state.error) {
      return (
        <div className="m-4 rounded-2xl bg-white p-6 shadow ring-1 ring-rose-200">
          <div className="text-lg font-bold text-rose-700">⚠️ Une erreur est survenue dans cette page</div>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-rose-50 p-3 text-xs text-rose-800">
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <button onClick={this.reset} className="mt-4 rounded-xl bg-[#1a3a5c] px-4 py-2 text-sm font-bold text-white hover:bg-[#234d77]">
            Réessayer
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
