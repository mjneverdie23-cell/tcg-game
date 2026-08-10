import { beforeEach, describe, expect, it } from 'vitest';
import { useNavigationStore } from './navigation';

describe('navigation store', () => {
  beforeEach(() => {
    useNavigationStore.setState({ screen: 'menu', stack: [] });
  });

  it('starts on the main menu', () => {
    expect(useNavigationStore.getState().screen).toBe('menu');
  });

  it('navigates and retraces the visited path with back()', () => {
    const { navigate } = useNavigationStore.getState();
    navigate('settings');
    navigate('shop');
    expect(useNavigationStore.getState().screen).toBe('shop');

    useNavigationStore.getState().back();
    expect(useNavigationStore.getState().screen).toBe('settings');
    useNavigationStore.getState().back();
    expect(useNavigationStore.getState().screen).toBe('menu');
  });

  it('ignores navigation to the current screen', () => {
    useNavigationStore.getState().navigate('menu');
    expect(useNavigationStore.getState().stack).toEqual([]);
  });

  it('falls back to the menu when back() is pressed with an empty stack', () => {
    useNavigationStore.setState({ screen: 'settings', stack: [] });
    useNavigationStore.getState().back();
    expect(useNavigationStore.getState().screen).toBe('menu');
  });
});
