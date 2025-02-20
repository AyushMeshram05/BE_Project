import React from 'react';
import { Home, Info, Map, Menu, X } from 'lucide-react';
import { useState } from 'react';

function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <nav className="bg-indigo-600 text-white">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-2">
            <Map className="h-6 w-6" />
            <span className="font-bold text-lg">Smart City Guide</span>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex space-x-8">
            <a href="#" className="flex items-center space-x-1 hover:text-indigo-200 transition">
              <Home className="h-4 w-4" />
              <span>Home</span>
            </a>
            <a href="#about" className="flex items-center space-x-1 hover:text-indigo-200 transition">
              <Info className="h-4 w-4" />
              <span>About</span>
            </a>
          </div>

          {/* Mobile Menu Button */}
          <button 
            className="md:hidden"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden pb-4">
            <a href="#" className="block py-2 hover:text-indigo-200 transition">
              <div className="flex items-center space-x-2">
                <Home className="h-4 w-4" />
                <span>Home</span>
              </div>
            </a>
            <a href="#about" className="block py-2 hover:text-indigo-200 transition">
              <div className="flex items-center space-x-2">
                <Info className="h-4 w-4" />
                <span>About</span>
              </div>
            </a>
          </div>
        )}
      </div>
    </nav>
  );
}

export default Navbar;