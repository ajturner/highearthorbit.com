<?php
/**
 * Plugin Name: High Earth Orbit content model
 * Description: Post types, fields, publishing endpoints and display helpers for highearthorbit.com. Deployed from the highearthorbit-content repository; edit it there, not on the server.
 * Version: 1.0.0
 * Requires at least: 6.9
 * Requires PHP: 8.1
 *
 * Content is published by the repository's publish job through two REST routes:
 *   POST /wp-json/heo/v1/upsert  create or update one item, matched by its source_id
 *   GET  /wp-json/heo/v1/index   list every managed item with its stored content hash
 */

defined( 'ABSPATH' ) || exit;

const HEO_TYPES = array( 'post', 'external_article', 'talk', 'project', 'photo_album' );

/**
 * Meta fields per post type: key => type. Every key is stored as heo_<key>.
 * Fields shared by all types are listed under '*'.
 */
function heo_fields(): array {
	return array(
		'*'                => array(
			'source_id' => 'string',
			'featured'  => 'boolean',
			'summary'   => 'string',
			'synced'    => 'string', // JSON written by sync jobs.
		),
		'post'             => array( 'legacy_url' => 'string' ),
		'external_article' => array(
			'publication' => 'string',
			'url'         => 'string',
		),
		'talk'             => array(
			'event'       => 'string',
			'location'    => 'string',
			'youtube_id'  => 'string',
			'video_url'   => 'string',
			'slides_url'  => 'string',
			'writeup_url' => 'string',
		),
		'project'          => array(
			'era'         => 'string',
			'role'        => 'string',
			'status'      => 'string',
			'year'        => 'integer',
			'repo'        => 'string',
			'demo'        => 'string',
			'writeup_url' => 'string',
			'github'      => 'string',
		),
		'photo_album'      => array(
			'flickr_id' => 'string',
			'place'     => 'string',
		),
	);
}

function heo_fields_for( string $post_type ): array {
	$all = heo_fields();
	return array_merge( $all['*'], $all[ $post_type ] ?? array() );
}

/* -------------------------------------------------------------------------
 * Post types and fields
 * ---------------------------------------------------------------------- */

add_action(
	'init',
	function () {
		$common = array(
			'public'       => true,
			'show_in_rest' => true,
			'menu_icon'    => 'dashicons-portfolio',
			'supports'     => array( 'title', 'editor', 'excerpt', 'thumbnail', 'custom-fields', 'revisions' ),
			'taxonomies'   => array( 'post_tag' ),
		);

		register_post_type(
			'project',
			array_merge(
				$common,
				array(
					'labels'      => array( 'name' => 'Projects', 'singular_name' => 'Project' ),
					'has_archive' => 'projects',
					'rewrite'     => array( 'slug' => 'projects', 'with_front' => false ),
					'menu_icon'   => 'dashicons-hammer',
				)
			)
		);
		register_post_type(
			'talk',
			array_merge(
				$common,
				array(
					'labels'      => array( 'name' => 'Talks', 'singular_name' => 'Talk' ),
					'has_archive' => 'talks',
					'rewrite'     => array( 'slug' => 'talks', 'with_front' => false ),
					'menu_icon'   => 'dashicons-microphone',
				)
			)
		);
		register_post_type(
			'photo_album',
			array_merge(
				$common,
				array(
					'labels'      => array( 'name' => 'Photo albums', 'singular_name' => 'Photo album' ),
					'has_archive' => 'photos',
					'rewrite'     => array( 'slug' => 'photos', 'with_front' => false ),
					'menu_icon'   => 'dashicons-format-gallery',
				)
			)
		);
		// External articles link out to their canonical URL; they appear in the writing list.
		register_post_type(
			'external_article',
			array_merge(
				$common,
				array(
					'labels'      => array( 'name' => 'External articles', 'singular_name' => 'External article' ),
					'has_archive' => false,
					'rewrite'     => array( 'slug' => 'external', 'with_front' => false ),
					'menu_icon'   => 'dashicons-external',
				)
			)
		);

		foreach ( HEO_TYPES as $type ) {
			foreach ( heo_fields_for( $type ) as $key => $kind ) {
				register_post_meta(
					$type,
					"heo_$key",
					array(
						'type'          => $kind,
						'single'        => true,
						'show_in_rest'  => 'synced' !== $key,
						'auth_callback' => fn() => current_user_can( 'edit_posts' ),
					)
				);
			}
		}

		heo_register_blocks();
	}
);

/* -------------------------------------------------------------------------
 * Publishing endpoints
 * ---------------------------------------------------------------------- */

add_action(
	'rest_api_init',
	function () {
		register_rest_route(
			'heo/v1',
			'/upsert',
			array(
				'methods'             => 'POST',
				'callback'            => 'heo_rest_upsert',
				'permission_callback' => fn() => current_user_can( 'edit_posts' ) && current_user_can( 'publish_posts' ),
			)
		);
		register_rest_route(
			'heo/v1',
			'/index',
			array(
				'methods'             => 'GET',
				'callback'            => 'heo_rest_index',
				'permission_callback' => fn() => current_user_can( 'edit_posts' ),
			)
		);
	}
);

/** Find the post that carries this source_id, in any status except trash. */
function heo_find_by_source_id( string $type, string $source_id ): ?WP_Post {
	$found = get_posts(
		array(
			'post_type'        => $type,
			'post_status'      => array( 'publish', 'draft', 'pending', 'private', 'future' ),
			'meta_key'         => 'heo_source_id',
			'meta_value'       => $source_id,
			'posts_per_page'   => 1,
			'no_found_rows'    => true,
			'suppress_filters' => true,
		)
	);
	return $found[0] ?? null;
}

function heo_rest_upsert( WP_REST_Request $req ) {
	$p         = $req->get_json_params();
	$type      = (string) ( $p['type'] ?? '' );
	$source_id = (string) ( $p['source_id'] ?? '' );

	if ( ! in_array( $type, HEO_TYPES, true ) ) {
		return new WP_Error( 'heo_bad_type', "Unknown type '$type'", array( 'status' => 400 ) );
	}
	if ( ! preg_match( '~^[a-z0-9][a-z0-9:._/-]{2,120}$~', $source_id ) ) {
		return new WP_Error( 'heo_bad_source_id', 'Missing or invalid source_id', array( 'status' => 400 ) );
	}

	$action   = 'updated';
	$existing = heo_find_by_source_id( $type, $source_id );
	if ( ! $existing && ! empty( $p['wp_id'] ) ) {
		$candidate = get_post( (int) $p['wp_id'] );
		if ( $candidate && $candidate->post_type === $type && 'trash' !== $candidate->post_status ) {
			$existing = $candidate;
			$action   = 'adopted';
		}
	}
	if ( ! $existing ) {
		$action = 'created';
	}

	$hash = (string) ( $p['hash'] ?? '' );
	if ( $existing && $hash && get_post_meta( $existing->ID, '_heo_hash', true ) === $hash && empty( $p['force'] ) ) {
		return array(
			'id'     => $existing->ID,
			'status' => $existing->post_status,
			'action' => 'unchanged',
			'link'   => get_permalink( $existing ),
		);
	}

	// Status rules: hidden items are drafts. An existing item keeps whatever status
	// it has in WordPress (so publishing a draft in wp-admin sticks), unless it was
	// a draft only because it was hidden. New items take new_status (default draft).
	$hidden     = ! empty( $p['hidden'] );
	$new_status = in_array( $p['new_status'] ?? 'draft', array( 'draft', 'publish' ), true ) ? $p['new_status'] : 'draft';
	if ( $hidden ) {
		$status = 'draft';
	} elseif ( $existing && 'hidden' === get_post_meta( $existing->ID, '_heo_draft_reason', true ) ) {
		$status = $new_status;
	} elseif ( $existing ) {
		$status = $existing->post_status;
	} else {
		$status = $new_status;
	}

	$postarr = array(
		'post_type'    => $type,
		'post_title'   => wp_strip_all_tags( (string) ( $p['title'] ?? '' ) ),
		'post_content' => (string) ( $p['content'] ?? '' ),
		'post_excerpt' => (string) ( $p['excerpt'] ?? '' ),
		'post_status'  => $status,
	);
	if ( ! empty( $p['slug'] ) ) {
		$postarr['post_name'] = sanitize_title( $p['slug'] );
	}
	if ( ! empty( $p['date'] ) ) {
		$postarr['post_date']     = gmdate( 'Y-m-d H:i:s', strtotime( (string) $p['date'] ) );
		$postarr['post_date_gmt'] = get_gmt_from_date( $postarr['post_date'] );
		$postarr['edit_date']     = true;
	}

	if ( $existing ) {
		$postarr['ID'] = $existing->ID;
		$id            = wp_update_post( wp_slash( $postarr ), true );
	} else {
		$postarr['post_author'] = get_current_user_id();
		$id                     = wp_insert_post( wp_slash( $postarr ), true );
	}
	if ( is_wp_error( $id ) ) {
		return $id;
	}

	update_post_meta( $id, 'heo_source_id', $source_id );
	update_post_meta( $id, '_heo_hash', $hash );
	if ( $hidden ) {
		update_post_meta( $id, '_heo_draft_reason', 'hidden' );
	} else {
		delete_post_meta( $id, '_heo_draft_reason' );
	}

	$allowed = heo_fields_for( $type );
	foreach ( (array) ( $p['meta'] ?? array() ) as $key => $value ) {
		if ( ! isset( $allowed[ $key ] ) || 'source_id' === $key ) {
			continue;
		}
		if ( null === $value || '' === $value ) {
			delete_post_meta( $id, "heo_$key" );
			continue;
		}
		if ( 'synced' === $key && ! is_string( $value ) ) {
			$value = wp_json_encode( $value );
		}
		update_post_meta( $id, "heo_$key", wp_slash( $value ) );
	}

	if ( isset( $p['tags'] ) ) {
		wp_set_post_terms( $id, array_map( 'strval', (array) $p['tags'] ), 'post_tag' );
	}
	if ( 'post' === $type && isset( $p['categories'] ) ) {
		$cat_ids = array();
		foreach ( (array) $p['categories'] as $name ) {
			$term = term_exists( $name, 'category' ) ?: wp_insert_term( $name, 'category' );
			if ( ! is_wp_error( $term ) ) {
				$cat_ids[] = (int) ( $term['term_id'] ?? $term );
			}
		}
		if ( $cat_ids ) {
			wp_set_post_categories( $id, $cat_ids );
		}
	}

	$image = (string) ( $p['featured_image_url'] ?? '' );
	if ( $image && get_post_meta( $id, '_heo_featured_src', true ) !== $image ) {
		require_once ABSPATH . 'wp-admin/includes/media.php';
		require_once ABSPATH . 'wp-admin/includes/file.php';
		require_once ABSPATH . 'wp-admin/includes/image.php';
		$att = media_sideload_image( $image, $id, $postarr['post_title'], 'id' );
		if ( ! is_wp_error( $att ) ) {
			set_post_thumbnail( $id, $att );
			update_post_meta( $id, '_heo_featured_src', $image );
		}
	}

	return array(
		'id'     => $id,
		'status' => get_post_status( $id ),
		'action' => $action,
		'link'   => get_permalink( $id ),
	);
}

function heo_rest_index( WP_REST_Request $req ) {
	$q   = new WP_Query(
		array(
			'post_type'      => HEO_TYPES,
			'post_status'    => array( 'publish', 'draft', 'pending', 'private', 'future' ),
			'meta_key'       => 'heo_source_id',
			'posts_per_page' => -1,
			'no_found_rows'  => true,
		)
	);
	$out = array();
	foreach ( $q->posts as $post ) {
		$out[] = array(
			'source_id' => get_post_meta( $post->ID, 'heo_source_id', true ),
			'id'        => $post->ID,
			'type'      => $post->post_type,
			'status'    => $post->post_status,
			'hash'      => get_post_meta( $post->ID, '_heo_hash', true ),
			'modified'  => $post->post_modified_gmt,
		);
	}
	return $out;
}

/* -------------------------------------------------------------------------
 * Front-end behavior
 * ---------------------------------------------------------------------- */

// External articles: link straight to the canonical URL, and redirect if their own page is opened.
add_filter(
	'post_type_link',
	function ( $link, $post ) {
		if ( 'external_article' === $post->post_type ) {
			$url = get_post_meta( $post->ID, 'heo_url', true );
			return $url ?: $link;
		}
		return $link;
	},
	10,
	2
);
add_action(
	'template_redirect',
	function () {
		if ( is_singular( 'external_article' ) ) {
			$url = get_post_meta( get_queried_object_id(), 'heo_url', true );
			if ( $url ) {
				wp_redirect( esc_url_raw( $url ), 301 );
				exit;
			}
		}
	}
);

// The writing list (posts page and its feed) includes external articles.
add_action(
	'pre_get_posts',
	function ( WP_Query $q ) {
		if ( ! is_admin() && $q->is_main_query() && ( $q->is_home() || ( $q->is_feed() && ! $q->get( 'post_type' ) ) ) ) {
			$q->set( 'post_type', array( 'post', 'external_article' ) );
		}
	}
);

// Query Loop blocks opt into extra filtering through their "namespace" attribute.
add_filter(
	'query_loop_block_query_vars',
	function ( $query, $block ) {
		$ns = $block->context['query']['namespace'] ?? '';
		if ( 'heo/writing' === $ns ) {
			$query['post_type'] = array( 'post', 'external_article' );
		} elseif ( 'heo/featured' === $ns ) {
			$query['meta_query'] = array(
				array(
					'key'   => 'heo_featured',
					'value' => '1',
				),
			);
		} elseif ( 'heo/not-featured' === $ns ) {
			$query['meta_query'] = array(
				'relation' => 'OR',
				array(
					'key'     => 'heo_featured',
					'compare' => 'NOT EXISTS',
				),
				array(
					'key'     => 'heo_featured',
					'value'   => '1',
					'compare' => '!=',
				),
			);
		}
		return $query;
	},
	10,
	2
);

/* -------------------------------------------------------------------------
 * Display helpers: block bindings and server-rendered blocks
 * ---------------------------------------------------------------------- */

function heo_synced( int $id ): array {
	$raw = get_post_meta( $id, 'heo_synced', true );
	$val = $raw ? json_decode( $raw, true ) : null;
	return is_array( $val ) ? $val : array();
}

/** Short uppercase line shown above a title, e.g. "ESRI · JAVASCRIPT · 713 STARS". */
function heo_kicker( int $id ): string {
	$type  = get_post_type( $id );
	$m     = fn( $k ) => (string) get_post_meta( $id, "heo_$k", true );
	$s     = heo_synced( $id );
	$parts = array();
	switch ( $type ) {
		case 'external_article':
			$parts = array( 'External', $m( 'publication' ), get_the_date( 'M j, Y', $id ) );
			break;
		case 'talk':
			$parts = array( $m( 'event' ), get_the_date( 'Y', $id ) );
			break;
		case 'project':
			$parts = array( $m( 'era' ), $s['language'] ?? '', isset( $s['stars'] ) ? number_format_i18n( (int) $s['stars'] ) . ' stars' : $m( 'year' ) );
			break;
		case 'photo_album':
			$parts = array( $m( 'place' ), isset( $s['count'] ) ? number_format_i18n( (int) $s['count'] ) . ' photos' : '' );
			break;
		default:
			$cats  = get_the_category( $id );
			$cats  = array_values( array_filter( $cats, fn( $c ) => 'uncategorized' !== $c->slug ) );
			$parts = array( get_the_date( 'M j, Y', $id ), $cats ? $cats[0]->name : '' );
	}
	return strtoupper( implode( ' · ', array_filter( array_map( 'trim', $parts ) ) ) );
}

function heo_binding_value( array $args, WP_Block $block ) {
	$id = (int) ( $block->context['postId'] ?? get_the_ID() );
	if ( ! $id ) {
		return null;
	}
	$key = (string) ( $args['key'] ?? '' );
	$s   = heo_synced( $id );
	switch ( $key ) {
		case 'kicker':
			return esc_html( heo_kicker( $id ) );
		case 'summary':
			$v = get_post_meta( $id, 'heo_summary', true ) ?: get_the_excerpt( $id );
			return esc_html( $v );
		case 'cover_url':
			return esc_url( get_the_post_thumbnail_url( $id, 'large' ) ?: ( $s['cover_url'] ?? '' ) );
		case 'flickr_url':
			return esc_url( $s['url'] ?? '' );
		default:
			if ( str_starts_with( $key, 'meta:' ) ) {
				return esc_html( (string) get_post_meta( $id, 'heo_' . substr( $key, 5 ), true ) );
			}
	}
	return null;
}

function heo_register_blocks(): void {
	if ( function_exists( 'register_block_bindings_source' ) ) {
		register_block_bindings_source(
			'heo/field',
			array(
				'label'              => 'High Earth Orbit field',
				'get_value_callback' => 'heo_binding_value',
				'uses_context'       => array( 'postId', 'postType' ),
			)
		);
	}

	$blocks = array(
		'heo/video'      => 'heo_render_video',
		'heo/item-links' => 'heo_render_item_links',
		'heo/photo-grid' => 'heo_render_photo_grid',
	);
	foreach ( $blocks as $name => $render ) {
		register_block_type(
			$name,
			array(
				'api_version'     => 3,
				'title'           => ucwords( str_replace( array( 'heo/', '-' ), array( '', ' ' ), $name ) ),
				'category'        => 'theme',
				'uses_context'    => array( 'postId', 'postType' ),
				'render_callback' => $render,
				'editor_script'   => 'heo-blocks-editor',
				'supports'        => array( 'html' => false ),
			)
		);
	}

	// Minimal editor registration so the Site Editor previews these blocks with server rendering.
	wp_register_script( 'heo-blocks-editor', false, array( 'wp-blocks', 'wp-element', 'wp-server-side-render' ), '1.0.0', true );
	$names = wp_json_encode( array_keys( $blocks ) );
	wp_add_inline_script(
		'heo-blocks-editor',
		"($names).forEach(function(n){wp.blocks.registerBlockType(n,{apiVersion:3,title:n,category:'theme',edit:function(p){return wp.element.createElement(wp.serverSideRender,{block:n,urlQueryArgs:{post_id:p.context&&p.context.postId}})},save:function(){return null}})});"
	);
}

function heo_block_post_id( $block ): int {
	return (int) ( $block->context['postId'] ?? get_the_ID() );
}

function heo_render_video( $attrs, $content, $block ): string {
	$id  = heo_block_post_id( $block );
	$yt  = (string) get_post_meta( $id, 'heo_youtube_id', true );
	$url = (string) get_post_meta( $id, 'heo_video_url', true );
	if ( preg_match( '/^[A-Za-z0-9_-]{11}$/', $yt ) ) {
		return sprintf(
			'<div class="heo-video"><iframe src="https://www.youtube-nocookie.com/embed/%s" title="%s" loading="lazy" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>',
			esc_attr( $yt ),
			esc_attr( get_the_title( $id ) )
		);
	}
	if ( $url ) {
		return sprintf( '<p class="heo-video-link"><a href="%s">Watch the video</a></p>', esc_url( $url ) );
	}
	return '';
}

function heo_render_item_links( $attrs, $content, $block ): string {
	$id    = heo_block_post_id( $block );
	$m     = fn( $k ) => (string) get_post_meta( $id, "heo_$k", true );
	$s     = heo_synced( $id );
	$links = array(
		'Repository' => $m( 'repo' ),
		'Demo'       => $m( 'demo' ) ?: ( $s['homepage'] ?? '' ),
		'Write-up'   => $m( 'writeup_url' ),
		'Slides'     => $m( 'slides_url' ),
		'Video'      => $m( 'youtube_id' ) ? '' : $m( 'video_url' ),
		'Album on Flickr' => $s['url'] ?? '',
	);
	$html = '';
	foreach ( array_filter( $links ) as $label => $href ) {
		$html .= sprintf( '<a href="%s">%s</a>', esc_url( $href ), esc_html( $label ) );
	}
	return $html ? '<p class="heo-item-links">' . $html . '</p>' : '';
}

function heo_render_photo_grid( $attrs, $content, $block ): string {
	$s      = heo_synced( heo_block_post_id( $block ) );
	$photos = $s['photos'] ?? array();
	if ( ! $photos ) {
		return '';
	}
	$html = '<div class="heo-photo-grid">';
	foreach ( $photos as $ph ) {
		$html .= sprintf(
			'<figure><a href="%s"><img src="%s" alt="%s" loading="lazy" width="%d" height="%d"></a></figure>',
			esc_url( $ph['page_url'] ?? '' ),
			esc_url( $ph['src'] ?? '' ),
			esc_attr( $ph['title'] ?? '' ),
			(int) ( $ph['width'] ?? 0 ),
			(int) ( $ph['height'] ?? 0 )
		);
	}
	$html .= '</div>';
	if ( ! empty( $s['url'] ) ) {
		$html .= sprintf( '<p class="heo-photo-credit"><a href="%s">View the full album on Flickr</a></p>', esc_url( $s['url'] ) );
	}
	return $html;
}
