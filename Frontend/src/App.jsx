import React from 'react';
import { Link, Routes, Route } from 'react-router-dom';
import RecommendationViewer from './components/RecommendationViewer';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import { BrowserRouter } from 'react-router-dom';

function App() {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Navbar />
      <main className="flex-grow">
        <RecommendationViewer />
      </main>
      <Footer />
    </div>
  );
}

export default App;