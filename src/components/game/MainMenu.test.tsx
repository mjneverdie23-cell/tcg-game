import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import App from '../../App';
import { useNavigationStore } from '../../stores/navigation';

describe('main menu', () => {
  beforeEach(() => {
    useNavigationStore.setState({ screen: 'menu', stack: [] });
  });

  it('renders the title and all menu entries', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'PRIMORDIA' })).toBeInTheDocument();
    for (const label of ['Battle', 'Collection', 'Deck Builder', 'Open Packs', 'Shop', 'Settings']) {
      expect(screen.getByRole('button', { name: new RegExp(label) })).toBeInTheDocument();
    }
  });

  it('disables entries whose screens are not implemented yet', () => {
    render(<App />);
    expect(screen.getByRole('button', { name: /Settings/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Battle/ })).toBeDisabled();
  });

  it('navigates to settings and back', () => {
    render(<App />);
    screen.getByRole('button', { name: /Settings/ }).click();
    expect(useNavigationStore.getState().screen).toBe('settings');
    useNavigationStore.getState().back();
    expect(useNavigationStore.getState().screen).toBe('menu');
  });
});
