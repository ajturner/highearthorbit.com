<?php
/**
 * High Earth Orbit theme setup.
 */

defined( 'ABSPATH' ) || exit;

add_action(
	'wp_enqueue_scripts',
	function () {
		wp_enqueue_style(
			'heo-fonts',
			'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap',
			array(),
			null
		);
		wp_enqueue_style( 'heo', get_stylesheet_uri(), array( 'heo-fonts' ), wp_get_theme()->get( 'Version' ) );
	}
);

add_action(
	'after_setup_theme',
	function () {
		add_editor_style( 'style.css' );
		add_theme_support( 'automatic-feed-links' );
	}
);
